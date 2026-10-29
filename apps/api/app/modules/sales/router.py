"""Sales HTTP routes: storefront cart/checkout, orders, payments, webhook."""
from decimal import Decimal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_CART_CHECKOUT, P_SALES_FULFILL, P_SALES_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.sales import service as svc
from app.modules.sales.models import OrderLine, SalesOrder

router = APIRouter(prefix="/storefront")


class CartItemIn(BaseModel):
    product_id: str
    qty: Decimal = Field(gt=0)


class CartItemQtyIn(BaseModel):
    qty: Decimal


class CartOut(BaseModel):
    id: str
    status: str
    items: list[dict]
    quote: dict


class CheckoutIn(BaseModel):
    customer_id: str
    shipping_address: str | None = None
    billing_address: str | None = None
    shipping_total: Decimal = Decimal("0")
    notes: str | None = None


class PayIn(BaseModel):
    method: str = "mock_gateway"
    provider: str = "mock"



def _cart_out(session: Session, cart) -> CartOut:
    quote = svc.quote_cart(session, cart)
    items = svc.cart_items(session, cart.id)
    return CartOut(
        id=cart.id,
        status=cart.status,
        items=[{"id": i.id, "product_id": i.product_id, "qty": str(i.qty)} for i in items],
        quote=quote,
    )


# ---- cart ----
@router.get("/cart", response_model=CartOut)
def get_cart(
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    from app.modules.partners import service as partners

    customer = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer.id if customer else None, token=None)
    return _cart_out(session, cart)


@router.post("/cart/items", response_model=CartOut)
def add_item(
    payload: CartItemIn,
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    from app.modules.partners import service as partners

    customer = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer.id if customer else None, token=None)
    svc.add_cart_item(session, cart, payload.product_id, payload.qty)
    return _cart_out(session, cart)


@router.patch("/cart/items/{item_id}", response_model=CartOut)
def update_item(
    item_id: str,
    payload: CartItemQtyIn,
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    from app.modules.partners import service as partners

    customer = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer.id if customer else None, token=None)
    svc.update_cart_item(session, cart, item_id, payload.qty)
    return _cart_out(session, cart)


@router.delete("/cart/items/{item_id}", response_model=CartOut)
def remove_item(
    item_id: str,
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    from app.modules.partners import service as partners

    customer = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer.id if customer else None, token=None)
    svc.remove_cart_item(session, cart, item_id)
    return _cart_out(session, cart)


@router.get("/cart/quote")
def quote(shipping_total: Decimal = Decimal("0"), ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)), session: Session = Depends(get_db)):
    from app.modules.partners import service as partners

    customer = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer.id if customer else None, token=None)
    return svc.quote_cart(session, cart, shipping_total=shipping_total)


# ---- checkout / orders ----
@router.post("/checkout")
def checkout(
    payload: CheckoutIn,
    x_idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    from app.modules.partners import service as partners

    customer = partners.get_customer(session, ctx.company_id, payload.customer_id)
    # resolve cart from user
    customer_user = partners.get_customer_by_user(session, ctx.company_id, ctx.user.id)
    customer_id = customer_user.id if customer_user else customer.id
    from app.modules.sales.models import Cart

    cart = session.scalar(
        select(Cart).where(Cart.company_id == ctx.company_id, Cart.user_id == ctx.user.id, Cart.status == "open")
    )
    if cart is None:
        cart = svc.get_or_create_cart(session, company_id=ctx.company_id, user_id=ctx.user.id, customer_id=customer_id, token=None)

    order, replayed = svc.checkout_cart(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        cart_id=cart.id,
        customer_id=customer_id,
        shipping_address=payload.shipping_address,
        billing_address=payload.billing_address,
        shipping_total=payload.shipping_total,
        notes=payload.notes,
        idempotency_key=x_idempotency_key,
    )
    return {
        "order_id": order.id,
        "doc_number": order.doc_number,
        "status": order.status,
        "total": str(order.total),
        "replayed": replayed,
    }


@router.post("/orders/{order_id}/pay")
def pay_order(
    order_id: str,
    payload: PayIn,
    x_idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: CompanyCtx = Depends(guard(P_CART_CHECKOUT)),
    session: Session = Depends(get_db),
):
    order, payment = svc.pay_order(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        order_id=order_id,
        method=payload.method,
        provider_name=payload.provider,
        idempotency_key=x_idempotency_key,
    )
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_state": order.payment_state,
        "invoice_id": order.invoice_id,
        "payment_ref": payment.provider_ref if payment else None,
    }


# The old authenticated POST /storefront/webhook/payment stub is gone: provider
# servers cannot authenticate with a bearer token, so webhooks now live at
# POST /api/v1/payments/webhooks/{provider}/{company_id} and authenticate with
# the provider's own signature (modules/payments/webhooks.py).


@router.get("/orders", response_model=list[dict])
def list_orders(
    status: str | None = None,
    customer_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_SALES_VIEW)),
    session: Session = Depends(get_db),
):
    orders = svc.list_orders(session, ctx.company_id, status=status, customer_id=customer_id)
    return [_order_brief(o) for o in orders]


@router.get("/orders/{order_id}")
def get_order(order_id: str, ctx: CompanyCtx = Depends(guard(P_SALES_VIEW)), session: Session = Depends(get_db)):
    order = svc.get_order(session, ctx.company_id, order_id)
    lines = svc.get_order_lines(session, order.id)
    data = _order_brief(order)
    data["lines"] = [
        {
            "id": l.id, "product_id": l.product_id, "sku": l.sku_snapshot,
            "qty": str(l.qty), "unit_price": str(l.unit_price),
            "line_total": str(l.line_total), "tax_amount": str(l.tax_amount),
        }
        for l in lines
    ]
    return data


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, ctx: CompanyCtx = Depends(guard(P_SALES_VIEW)), session: Session = Depends(get_db)):
    order = svc.get_order(session, ctx.company_id, order_id)
    svc.cancel_order(session, order, ctx.user.id)
    log_action(session, action="order.cancelled", entity_type="sales_order", entity_id=order.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return {"id": order.id, "status": order.status}


def _order_brief(order: SalesOrder) -> dict:
    return {
        "id": order.id,
        "doc_number": order.doc_number,
        "customer_id": order.customer_id,
        "status": order.status,
        "payment_state": order.payment_state,
        "order_date": str(order.order_date),
        "currency": order.currency,
        "subtotal": str(order.subtotal),
        "tax_total": str(order.tax_total),
        "shipping_total": str(order.shipping_total),
        "total": str(order.total),
        "invoice_id": order.invoice_id,
        "shipping_address": order.shipping_address,
    }
