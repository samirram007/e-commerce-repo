"""Sales service: carts, checkout (idempotent, stock-reserving), payment and
order lifecycle. Backend recomputes prices/taxes — client values are ignored.
"""
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import new_id
from app.modules.accounting import service as accounting
from app.modules.catalog import service as catalog
from app.modules.companies import service as companies
from app.modules.companies.models import Company
from app.modules.inventory import service as inventory
from app.modules.invoicing import service as invoicing
from app.modules.payments import service as payments
from app.modules.payments.models import PaymentRecord
from app.modules.partners import service as partners
from app.modules.promotions import service as promotions
from app.modules.sales.models import (
    ORDER_STATUSES,
    Cart,
    CartItem,
    OrderLine,
    SalesOrder,
)
from app.modules.taxes import service as taxes
from app.modules.taxes.models import TaxRate
from app.shared.idempotency import run_idempotent
from app.shared.money import dec, money
from app.shared.numbering import allocate_number


def _company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    return company


# ---- carts ----
def get_or_create_cart(
    session: Session, *, company_id: str, user_id: str | None, customer_id: str | None, token: str | None
) -> Cart:
    stmt = select(Cart).where(Cart.company_id == company_id, Cart.status == "open")
    if user_id:
        cart = session.scalar(stmt.where(Cart.user_id == user_id))
    elif token:
        cart = session.scalar(stmt.where(Cart.token == token))
    else:
        raise BusinessRuleError("CART_IDENTITY_REQUIRED", "Cart requires a user or guest token")
    if cart is None:
        cart = Cart(company_id=company_id, user_id=user_id, customer_id=customer_id, token=token)
        session.add(cart)
        session.flush()
    if customer_id and cart.customer_id is None:
        cart.customer_id = customer_id
        session.flush()
    return cart


def get_cart(session: Session, company_id: str, cart_id: str) -> Cart:
    cart = session.get(Cart, cart_id)
    if cart is None or cart.company_id != company_id:
        raise NotFoundError("Cart")
    if cart.status != "open":
        raise BusinessRuleError("CART_CLOSED", "Cart is not open")
    return cart


def cart_items(session: Session, cart_id: str) -> list[CartItem]:
    return list(session.execute(select(CartItem).where(CartItem.cart_id == cart_id)).scalars())


def add_cart_item(session: Session, cart: Cart, product_id: str, quantity) -> CartItem:
    from app.shared.money import qty as q4

    quantity = q4(dec(quantity))
    if quantity <= 0:
        raise BusinessRuleError("BAD_QTY", "Quantity must be > 0")
    product = session.get(catalog_models(), product_id)
    if product is None or product.company_id != cart.company_id:
        raise NotFoundError("Product")
    if not product.is_sellable or not product.is_active:
        raise BusinessRuleError("NOT_SELLABLE", f"Product {product.sku} cannot be purchased")
    item = session.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
    if item is None:
        item = CartItem(cart_id=cart.id, product_id=product_id, qty=quantity)
        session.add(item)
    else:
        item.qty = q4(dec(item.qty) + quantity)
    session.flush()
    return item


def catalog_models() -> object:
    from app.modules.catalog.models import Product

    return Product


def update_cart_item(session: Session, cart: Cart, item_id: str, quantity) -> CartItem:
    item = session.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise NotFoundError("Cart item")
    from app.shared.money import qty as q4

    quantity = q4(dec(quantity))
    if quantity <= 0:
        session.delete(item)
        session.flush()
        return None
    item.qty = quantity
    session.flush()
    return item


def remove_cart_item(session: Session, cart: Cart, item_id: str) -> None:
    item = session.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise NotFoundError("Cart item")
    session.delete(item)
    session.flush()


def quote_cart(
    session: Session,
    cart: Cart,
    *,
    shipping_total=Decimal("0"),
    customer_key: str | None = None,
    strict_coupon: bool = False,
) -> dict:
    """Server-side authoritative quote: price + tax per line, totals overall.

    The cart's own promo code is re-priced every time, so a code that stops
    qualifying (minimum subtotal, redemption limit, expiry) simply stops being
    applied — unless `strict_coupon` is set, which is what checkout uses to tell
    the shopper why instead of quietly charging full price.
    """
    company = _company(session, cart.company_id)
    default_tax_rate_id = taxes.default_sales_tax_id(session, company.id)
    default_tax = (
        dec(session.get(TaxRate, default_tax_rate_id).percentage) if default_tax_rate_id else Decimal("0")
    )
    today = datetime.now(timezone.utc).date()
    priced = []
    for item in cart_items(session, cart.id):
        product = session.get(catalog.Product, item.product_id)
        if product is None:
            raise NotFoundError("Product")
        unit_price = catalog.resolve_price(session, product, currency=company.base_currency, on_date=today)
        qty = dec(item.qty)
        priced.append(
            {
                "item_id": item.id,
                "product_id": product.id,
                "category_id": product.category_id,
                "sku": product.sku,
                "qty": qty,
                "unit_price": unit_price,
                "amount": money(qty * unit_price, 2),
            }
        )

    coupon = promotions.price(
        session,
        company.id,
        cart.coupon_code,
        [
            promotions.QuoteLine(
                product_id=row["product_id"],
                category_id=row["category_id"],
                amount=row["amount"],
            )
            for row in priced
        ],
        customer_key=customer_key,
        strict=strict_coupon,
    )

    lines = []
    subtotal = discount_total = tax_total = Decimal("0")
    for row in priced:
        discount = money(coupon.line_discounts.get(row["product_id"], Decimal("0")))
        # Tax follows the discounted taxable value, exactly as the invoice does.
        taxable = row["amount"] - discount
        tax_amount = money(taxable * default_tax / Decimal("100"), 2)
        line_total = money(taxable + tax_amount, 2)
        subtotal += row["amount"]
        discount_total += discount
        tax_total += tax_amount
        lines.append(
            {
                "item_id": row["item_id"],
                "product_id": row["product_id"],
                "sku": row["sku"],
                "qty": str(row["qty"]),
                "unit_price": str(row["unit_price"]),
                "discount": str(discount),
                "tax_amount": str(tax_amount),
                "line_total": str(line_total),
            }
        )
    shipping = money(dec(shipping_total), 2)
    total = money(subtotal - discount_total + tax_total + shipping, 2)
    # GST is charged at one rate here, so the breakup has a single slab; the UI
    # renders it as "GST 18% · CGST 9% + SGST 9%" instead of an unlabelled "Tax".
    tax_breakup = (
        [{"rate": str(default_tax), "amount": str(tax_total)}]
        if default_tax > 0 and tax_total > 0
        else []
    )
    return {
        "cart_id": cart.id,
        "lines": lines,
        "subtotal": str(subtotal),
        "discount_total": str(discount_total),
        "tax_total": str(tax_total),
        "tax_breakup": tax_breakup,
        "shipping_total": str(shipping),
        "total": str(total),
        "currency": company.base_currency,
        "coupon": coupon.as_dict() if coupon.code else None,
    }


# ---- checkout ----
def checkout_cart(
    session: Session, *, company_id: str, actor_user_id: str | None, cart_id: str,
    customer_id: str, shipping_address: str | None, billing_address: str | None,
    shipping_total=Decimal("0"), notes: str | None = None, idempotency_key: str,
) -> tuple[SalesOrder, bool]:
    """Idempotent checkout: creates the order and reserves stock atomically.
    Replays with the same key return the same order without side effects."""
    from app.core.security import new_id as gen_id

    def _execute() -> dict:
        order = _checkout_once(
            session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            cart_id=cart_id,
            customer_id=customer_id,
            shipping_address=shipping_address,
            billing_address=billing_address,
            shipping_total=shipping_total,
            notes=notes,
        )
        return {"id": order.id, "doc_number": order.doc_number, "status": order.status}

    result, replayed = run_idempotent(
        session,
        scope=f"checkout:{company_id}",
        key=idempotency_key,
        company_id=company_id,
        execute=_execute,
    )
    order = session.get(SalesOrder, result["id"])
    return order, replayed


def _checkout_once(
    session: Session, *, company_id: str, actor_user_id: str | None, cart_id: str,
    customer_id: str, shipping_address: str | None, billing_address: str | None,
    shipping_total, notes: str | None,
) -> SalesOrder:
    company = _company(session, company_id)
    cart = get_cart(session, company_id, cart_id)
    customer = partners.get_customer(session, company_id, customer_id)
    items = cart_items(session, cart.id)
    if not items:
        raise BusinessRuleError("EMPTY_CART", "Cart is empty")
    # Strict: a code that can no longer be used must fail here, with its reason,
    # rather than silently dropping off the order the shopper is paying for.
    quote = quote_cart(
        session,
        cart,
        shipping_total=shipping_total,
        customer_key=coupon_customer_key(actor_user_id, customer),
        strict_coupon=True,
    )

    doc_number = allocate_number(session, company_id, "sales_order")
    order = SalesOrder(
        company_id=company_id,
        doc_number=doc_number,
        customer_id=customer.id,
        user_id=actor_user_id,
        status="pending_payment",
        payment_state="unpaid",
        order_date=datetime.now(timezone.utc).date(),
        currency=company.base_currency,
        shipping_address=shipping_address,
        billing_address=billing_address,
        subtotal=Decimal(quote["subtotal"]),
        discount_total=Decimal(quote["discount_total"]),
        tax_total=Decimal(quote["tax_total"]),
        shipping_total=quote["shipping_total"],
        total=Decimal(quote["total"]),
        total_base=Decimal(quote["total"]),
        cart_id=cart.id,
        notes=notes,
    )
    session.add(order)
    session.flush()

    coupon_quote = quote.get("coupon") or {}
    coupon = None
    if coupon_quote.get("valid"):
        coupon = promotions.get_coupon(session, company_id, coupon_quote["code"])
        order.coupon_id = coupon.id if coupon else None
        order.coupon_code = coupon_quote["code"]
        promotions.redeem(
            session,
            coupon=coupon,
            order_id=order.id,
            amount=Decimal(coupon_quote["discount_total"]),
            customer_key=coupon_customer_key(actor_user_id, customer),
        )

    line_number = 1
    for line in quote["lines"]:
        product = session.get(catalog.Product, line["product_id"])
        stock_type = product.stock_type
        reserved_location = None
        if stock_type == "stock":
            if not inventory.check_availability(session, company_id=company_id, product_id=product.id, need=Decimal(line["qty"])):
                raise BusinessRuleError(
                    "OUT_OF_STOCK", f"Product {product.sku} is out of stock"
                )
            inventory.reserve_stock(
                session,
                company_id=company_id,
                product_id=product.id,
                quantity=Decimal(line["qty"]),
                source_type="sales_order",
                source_id=order.id,
                actor_user_id=actor_user_id,
            )
            reserved_location = _first_reserved_location(session, order.id, product.id)
        session.add(
            OrderLine(
                order_id=order.id,
                product_id=product.id,
                sku_snapshot=product.sku,
                description_snapshot=product.name,
                qty=Decimal(line["qty"]),
                unit_price=Decimal(line["unit_price"]),
                # the coupon's share of this line, so the invoice reproduces it
                discount=Decimal(line["discount"]),
                tax_percentage=default_sales_tax_percentage(session, company_id),
                line_total=Decimal(line["line_total"]),
                tax_amount=Decimal(line["tax_amount"]),
                line_number=line_number,
                reserved_location_id=reserved_location,
            )
        )
        line_number += 1

    cart.status = "converted"
    session.flush()
    return order


def coupon_customer_key(actor_user_id: str | None, customer) -> str | None:
    """Who counts as "one customer" for per-customer coupon limits."""
    if actor_user_id:
        return actor_user_id
    email = (getattr(customer, "email", None) or "").strip().lower()
    return email or None


def default_sales_tax_percentage(session: Session, company_id: str) -> Decimal:
    tax_rate_id = taxes.default_sales_tax_id(session, company_id)
    if tax_rate_id:
        return dec(session.get(TaxRate, tax_rate_id).percentage)
    return Decimal("0")


def _first_reserved_location(session: Session, order_id: str, product_id: str) -> str | None:
    from app.modules.inventory.models import StockLedgerEntry

    entry = session.scalar(
        select(StockLedgerEntry)
        .where(StockLedgerEntry.source_type == "sales_order", StockLedgerEntry.source_id == order_id, StockLedgerEntry.product_id == product_id, StockLedgerEntry.movement_type == "reserve")
        .order_by(StockLedgerEntry.id)
    )
    return entry.location_id if entry else None


# ---- payments ----
def pay_order(
    session: Session, *, company_id: str, actor_user_id: str | None, order_id: str,
    method: str = "mock_gateway", provider_name: str = "mock", idempotency_key: str,
) -> tuple[SalesOrder, PaymentRecord]:
    """Synchronous charge + confirm (authenticated /pay route).

    Creates the provider intent, verifies it immediately (the mock gateway
    always verifies; hosted gateways are confirmed through
    `confirm_order_payment` from the client callback or webhook), then
    finalizes the order — status paid, invoice issued and posted — exactly like
    the webhook path does. Idempotent by `idempotency_key`.
    """

    def _execute() -> dict:
        order, payment = _charge_once(
            session, company_id=company_id, actor_user_id=actor_user_id, order_id=order_id,
            method=method, provider_name=provider_name,
        )
        return {"order_id": order.id, "payment_id": payment.id if payment else None}

    result, replayed = run_idempotent(
        session,
        scope=f"pay:{company_id}",
        key=idempotency_key,
        company_id=company_id,
        execute=_execute,
    )
    order = session.get(SalesOrder, result["order_id"])
    return order, session.get(PaymentRecord, result["payment_id"]) if result.get("payment_id") else None


def confirm_order_payment(
    session: Session, *, company_id: str, actor_user_id: str | None, order_id: str,
    payment: PaymentRecord, charge_ref: str | None = None,
) -> tuple[SalesOrder, PaymentRecord]:
    """Finalize a payment the provider already confirmed (browser callback or
    webhook). Whichever arrives first completes the order; the other replays
    through the shared `pay:{order_id}` idempotency key — one payment row, one
    invoice, one journal.
    """
    payments.mark_succeeded(session, payment, charge_ref)

    def _execute() -> dict:
        order = _finalize_paid_order(session, company_id=company_id, order_id=order_id, actor_user_id=actor_user_id)
        return {"order_id": order.id, "payment_id": payment.id}

    result, _replayed = run_idempotent(
        session,
        scope=f"pay:{company_id}",
        key=f"pay:{order_id}",
        company_id=company_id,
        execute=_execute,
    )
    order = session.get(SalesOrder, result["order_id"])
    stored = session.get(PaymentRecord, result["payment_id"]) if result.get("payment_id") else payment
    return order, stored


def fail_order_payment(session: Session, payment: PaymentRecord, message: str | None = None) -> None:
    """Provider reported a failed payment: keep the order pending so the shopper
    can retry through the existing continue-purchase path."""
    payments.mark_failed(session, payment, message)


def _finalize_paid_order(
    session: Session, *, company_id: str, order_id: str, actor_user_id: str | None
) -> SalesOrder:
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    if order.status == "paid":
        return order
    if order.status != "pending_payment":
        raise BusinessRuleError("ORDER_NOT_PAYABLE", f"Order status '{order.status}' cannot be paid")
    order.payment_state = "paid"
    order.status = "paid"
    session.flush()
    _issue_invoice_for_paid_order(session, order, actor_user_id)
    return order


def _charge_once(
    session: Session, *, company_id: str, actor_user_id: str | None, order_id: str,
    method: str, provider_name: str,
) -> tuple[SalesOrder, PaymentRecord]:
    """Charge + confirm in one request (offline/mock-capable path)."""
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    if order.status != "pending_payment":
        raise BusinessRuleError("ORDER_NOT_PAYABLE", f"Order status '{order.status}' cannot be paid")

    from app.modules.payments.gateways import resolve_gateway

    adapter, creds, _config = resolve_gateway(session, company_id, method)
    record = payments.pending_for_order(session, order.id, adapter.name)
    if record is None:
        record, _intent = payments.create_provider_intent(
            session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            customer_id=order.customer_id,
            order_id=order.id,
            receipt=order.doc_number,
            amount=order.total,
            currency=order.currency,
            method=method,
            adapter=adapter,
            creds=creds,
            idempotency_key=f"intent:{order.id}",
        )
    verify = adapter.verify_client_payment(
        creds,
        payload={
            "order_id": record.provider_ref,
            "payment_intent_id": record.provider_ref,
            "razorpay_order_id": record.provider_ref,
        },
    )
    if not verify.succeeded:
        payments.mark_failed(session, record, verify.message)
        raise BusinessRuleError(
            "PAYMENT_DECLINED", f"{verify.error_code}: {verify.message}"
        )
    payments.mark_succeeded(session, record, verify.provider_ref)
    order = _finalize_paid_order(
        session, company_id=company_id, order_id=order_id, actor_user_id=actor_user_id
    )
    return order, record


def accept_cash_on_delivery(
    session: Session, *, company_id: str, order: SalesOrder, actor_user_id: str | None = None
) -> PaymentRecord:
    """Take a COD order: confirm it for fulfilment with an open cash receipt.

    Nothing is recognised yet — the invoice is issued when the courier hands the
    cash over (see `collect_cash_on_delivery`).
    """
    from app.modules.companies.service import rate_for

    company = _company(session, company_id)
    if order.status != "pending_payment":
        raise BusinessRuleError(
            "ORDER_NOT_PAYABLE", f"Order status '{order.status}' cannot be confirmed for COD"
        )
    existing = session.scalar(
        select(PaymentRecord).where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.provider == "cash",
            PaymentRecord.direction == "receipt",
        )
    )
    if existing is not None:
        return existing
    exchange_rate = dec(
        rate_for(
            session,
            company_id=company_id,
            from_currency=order.currency,
            base_currency=company.base_currency,
            on_date=order.order_date,
        )
    )
    record = PaymentRecord(
        company_id=company_id,
        direction="receipt",
        method="cod",
        provider="cash",
        provider_ref=f"cod:{order.id}",
        status="pending",
        amount=dec(order.total),
        currency=order.currency,
        exchange_rate=exchange_rate,
        amount_base=money(dec(order.total) * exchange_rate, 2),
        customer_id=order.customer_id,
        order_id=order.id,
        occurred_at=datetime.now(timezone.utc),
        idempotency_scope="cod",
        notes="Cash on delivery",
        created_by=actor_user_id,
    )
    session.add(record)
    order.status = "confirmed"
    session.flush()
    return record


def collect_cash_on_delivery(session: Session, *, order: SalesOrder) -> PaymentRecord | None:
    """Settle the pending COD record when the shipment is delivered.

    Revenue is recognised at that point (invoice issued + posted), matching the
    prepaid flow. Idempotent: a second delivery callback finds no pending row.
    """
    pending = session.scalar(
        select(PaymentRecord).where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.provider == "cash",
            PaymentRecord.direction == "receipt",
            PaymentRecord.status == "pending",
        )
    )
    if pending is None:
        return None
    pending.status = "succeeded"
    pending.occurred_at = datetime.now(timezone.utc)
    order.payment_state = "paid"
    session.flush()
    if order.invoice_id is None:
        _issue_invoice_for_paid_order(session, order, pending.created_by)
    return pending


def _issue_invoice_for_paid_order(session: Session, order: SalesOrder, actor_user_id: str | None) -> None:
    """Issue and post the invoice on payment confirmation."""
    company = _company(session, order.company_id)
    lines = session.execute(select(OrderLine).where(OrderLine.order_id == order.id).order_by(OrderLine.line_number)).scalars().all()
    invoice = invoicing.create_invoice(
        session,
        company_id=order.company_id,
        actor_user_id=actor_user_id,
        customer_id=order.customer_id,
        invoice_date=order.order_date,
        currency=order.currency,
        lines=[
            {
                "product_id": line.product_id,
                "description": line.description_snapshot,
                "qty": dec(line.qty),
                "unit_price": dec(line.unit_price),
                "discount": dec(line.discount),
                "tax_percentage": dec(line.tax_percentage),
            }
            for line in lines
        ],
        shipping_total=dec(order.shipping_total),
        order_id=order.id,
        source="order",
        # billing address snapshot: the printed GST invoice needs a buyer address
        customer_address=order.billing_address or order.shipping_address,
    )
    invoicing.post_invoice(session, invoice, actor_user_id)
    order.invoice_id = invoice.id
    session.flush()


# Provider webhooks are handled by modules/payments/webhooks.py: the old
# SECRET_KEY-HMAC stub was replaced by real per-provider signature verification.


# ---- later lifecycle: fulfillment transitions live in fulfillment module ----
def get_order(session: Session, company_id: str, order_id: str) -> SalesOrder:
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    return order


def get_order_lines(session: Session, order_id: str) -> list[OrderLine]:
    return list(
        session.execute(select(OrderLine).where(OrderLine.order_id == order_id).order_by(OrderLine.line_number)).scalars()
    )


def cancel_order(
    session: Session,
    order: SalesOrder,
    actor_user_id: str | None,
    cancel_reason: str | None = None,
) -> SalesOrder:
    """Cancel unpaid orders — reservations are released; paid orders must be
    refunded instead (returns module). `cancel_reason` is shown to the shopper."""
    if order.status == "cancelled":
        raise BusinessRuleError("ALREADY_CANCELLED", "Order is already cancelled")
    if order.payment_state == "paid":
        raise BusinessRuleError("PAID_ORDER_NOT_CANCELLABLE", "Use a refund for paid orders")
    contract_lines = get_order_lines(session, order.id)
    for line in contract_lines:
        if line.reserved_location_id is not None:
            inventory.release_reservation(
                session,
                company_id=order.company_id,
                product_id=line.product_id,
                quantity=line.qty,
                source_type="sales_order_cancel",
                source_id=order.id,
                actor_user_id=actor_user_id,
            )
            line.reserved_location_id = None
    # A cash-on-delivery order was never collected: close its open receipt.
    for pending in session.execute(
        select(PaymentRecord).where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.direction == "receipt",
            PaymentRecord.status == "pending",
        )
    ).scalars():
        pending.status = "voided"
        session.flush()
    order.status = "cancelled"
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancel_reason = cancel_reason
    session.flush()
    return order


def expire_unpaid_orders(
    session: Session, *, company_id: str | None = None, timeout_minutes: int | None = None
) -> int:
    """Cancel gateway orders that were never paid, releasing their stock holds.

    Only `pending_payment` orders are touched — COD orders sit in `confirmed`
    and paid orders are left alone, so a run never disturbs a real sale. Open
    payment intents are voided by `cancel_order`; replaying a sweep finds
    nothing and returns 0.
    """
    from app.core.config import get_settings

    minutes = (
        get_settings().order_payment_timeout_minutes
        if timeout_minutes is None
        else timeout_minutes
    )
    if minutes <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    stmt = select(SalesOrder).where(
        SalesOrder.status == "pending_payment",
        SalesOrder.payment_state != "paid",
        SalesOrder.created_at < cutoff,
    )
    if company_id is not None:
        stmt = stmt.where(SalesOrder.company_id == company_id)
    expired = 0
    for order in session.execute(stmt).scalars().all():
        cancel_order(session, order, None, cancel_reason="payment_timeout")
        expired += 1
    return expired


def list_orders(session: Session, company_id: str, *, status: str | None = None, customer_id: str | None = None, limit: int = 200):
    stmt = select(SalesOrder).where(SalesOrder.company_id == company_id).order_by(SalesOrder.order_date.desc()).limit(limit)
    if status:
        stmt = stmt.where(SalesOrder.status == status)
    if customer_id:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    return session.execute(stmt).scalars().all()
