"""Storefront HTTP routes — public (no auth required) shopping surface.

Every route needs an `X-Company-Id` header (which company's store this is) but
NOT a bearer token: guests browse, favorite and fill a token cart; checkout
still requires a signed-in customer (existing /storefront/checkout).
"""
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Header, Request, Response
<<<<<<< HEAD
=======
from fastapi.responses import FileResponse
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, BusinessRuleError, NotFoundError
from app.core.security import decode_token
from app.db.unit_of_work import get_db
<<<<<<< HEAD
from app.modules.catalog.models import Product
from app.modules.identity.models import User
=======
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
from app.modules.storefront import service as svc
from app.shared.files import open_file, open_public_file, StoredFile

router = APIRouter(prefix="/storefront/shop")


class StoreCtx:
    """Who is shopping: optional signed-in user, optional anonymous id."""

    def __init__(self, company_id: str, user_id: str | None, anon_id: str | None):
        self.company_id = company_id
        self.user_id = user_id
        self.anon_id = anon_id


def store_ctx(
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    authorization: str | None = Header(default=None),
    x_anon_id: str | None = Header(default=None, alias="X-Anon-Id"),
) -> StoreCtx:
    if not x_company_id:
        raise AuthError("company_required", "X-Company-Id header is required")
    user_id: str | None = None
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = decode_token(authorization[7:], expected_type="access")
            user_id = payload.get("sub")
        except Exception:
            user_id = None  # expired/invalid token → treat as guest, don't 401
    return StoreCtx(company_id=x_company_id, user_id=user_id, anon_id=x_anon_id)


def cart_token_header(x_cart_token: str | None = Header(default=None, alias="X-Cart-Token")) -> str:
    if not x_cart_token or len(x_cart_token) < 8:
        raise BusinessRuleError("CART_TOKEN_INVALID", "A stable X-Cart-Token (>= 8 chars) is required")
    return x_cart_token


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise BusinessRuleError("BAD_PRICE", f"'{value}' is not a valid number")


# ---- catalog ----
@router.get("/categories")
def categories(
    slug: str | None = None,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.list_categories(session, ctx.company_id, slug=slug)


@router.get("/products")
def products(
    q: str | None = None,
    category: str | None = None,
    min_price: str | None = None,
    max_price: str | None = None,
    on_sale: bool = False,
    badge: str | None = None,
    sort: str = "popular",
    limit: int = 24,
    offset: int = 0,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return svc.list_products(
        session,
        ctx.company_id,
        q=q,
        category=category,
        min_price=_to_decimal(min_price),
        max_price=_to_decimal(max_price),
        on_sale=on_sale,
        badge=badge,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}")
def product_detail(
    product_id: str,
    count_view: bool = False,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.product_detail(session, ctx.company_id, product_id, count_view=count_view)


@router.get(
    "/products/{product_id}/image",
    responses={200: {"content": {"image/svg+xml": {}}}},
)
def product_image(product_id: str, session: Session = Depends(get_db)):
    """Product tile for `<img>` tags, so it must stay public and header-free.

    Resolves the product by id alone (company scoping would require a header a
    browser cannot attach to an image request) and serves the deterministic
    generated tile. A real uploaded photo can take precedence here later.
    """
    product = session.get(Product, product_id)
    if product is None or not product.is_active:
        raise NotFoundError("Product image")
    return Response(
        content=svc.placeholder_image_svg(session, product),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/trending")
def trending(limit: int = 8, ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.trending(session, ctx.company_id, limit=max(1, min(limit, 24)))


# ---- home page bundle ----
@router.get("/home")
def home(ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    """Hero slides, featured categories, bestsellers/new arrivals, the deal
    of the day and testimonials — everything the home page renders."""
    return svc.home(session, ctx.company_id)


# ---- public info content ----
@router.get("/faqs")
def faqs(ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.list_faqs(session, ctx.company_id)


@router.get("/policies")
def policies(ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.list_policies(session, ctx.company_id)


@router.get("/policies/{slug}")
def policy(slug: str, ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.get_policy(session, ctx.company_id, slug)


# ---- interests ----
class InterestIn(BaseModel):
    kind: str = Field(pattern="^(favorite|watchlist)$")
    product_id: str


@router.post("/interests/toggle")
def toggle_interest(
    payload: InterestIn,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    active = svc.toggle_interest(
        session,
        ctx.company_id,
        payload.kind,
        payload.product_id,
        user_id=ctx.user_id,
        anon_id=ctx.anon_id,
    )
    return {"kind": payload.kind, "product_id": payload.product_id, "active": active}


@router.get("/interests")
def list_interests(ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.list_interests(session, ctx.company_id, user_id=ctx.user_id, anon_id=ctx.anon_id)


@router.post("/interests/claim")
def claim_interests(
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Attach all anonymous-id interests to the signed-in account (login time)."""
    if ctx.user_id is None:
        raise BusinessRuleError("LOGIN_REQUIRED", "Sign in to claim guest favorites")
    moved = svc.claim_anon_interests(
        session, ctx.company_id, anon_id=ctx.anon_id or "", user_id=ctx.user_id
    )
    return {"claimed": moved}


# ---- pincode delivery ----
@router.get("/pincode/{pincode}")
def pincode_check(pincode: str, ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    return svc.check_pincode(session, ctx.company_id, pincode)


# ---- guest token cart (browsing without login) ----
@router.get("/cart")
def guest_cart(
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.guest_cart_out(session, ctx.company_id, token)


class GuestCartItemIn(BaseModel):
    product_id: str
    qty: Decimal = Field(gt=0)


class GuestCartItemQtyIn(BaseModel):
    qty: Decimal


@router.post("/cart/items")
def guest_cart_add(
    payload: GuestCartItemIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    from app.modules.sales import service as sales_svc

    cart = svc.token_cart(session, ctx.company_id, token)
    sales_svc.add_cart_item(session, cart, payload.product_id, payload.qty)
    return svc.guest_cart_out(session, ctx.company_id, token)


@router.patch("/cart/items/{item_id}")
def guest_cart_patch(
    item_id: str,
    payload: GuestCartItemQtyIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    from app.modules.sales import service as sales_svc

    cart = svc.token_cart(session, ctx.company_id, token)
    sales_svc.update_cart_item(session, cart, item_id, payload.qty)
    return svc.guest_cart_out(session, ctx.company_id, token)


@router.delete("/cart/items/{item_id}")
def guest_cart_remove(
    item_id: str,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    from app.modules.sales import service as sales_svc

    cart = svc.token_cart(session, ctx.company_id, token)
    sales_svc.remove_cart_item(session, cart, item_id)
    return svc.guest_cart_out(session, ctx.company_id, token)


@router.delete("/cart")
def guest_cart_clear(
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    from app.modules.sales import service as sales_svc

    cart = svc.token_cart(session, ctx.company_id, token)
    for item in sales_svc.cart_items(session, cart.id):
        session.delete(item)
    session.flush()
    return svc.guest_cart_out(session, ctx.company_id, token)


# ---- file serving ----
@router.get("/files/{file_id}")
def serve_file(file_id: str, ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    """Serve a stored file to a company-scoped caller (invoices, receipts,
    private docs). Public storefront imagery goes through `/media/...` instead."""
    record, path = open_file(session, file_id, company_id=ctx.company_id)
    return FileResponse(path=path, media_type=record.content_type)


#: Storefront images are content-hashed by server-side key; cache hard.
MEDIA_CACHE_CONTROL = "public, max-age=31536000, immutable"


@router.get("/media/{company_id}/{file_id}")
def public_media(
    company_id: str,
    file_id: str,
    request: Request,
    session: Session = Depends(get_db),
):
    """Public storefront image route: no headers, no auth.

    Serves only files saved with `visibility="public"` for the company in the
    path (the same id every shop request is scoped to); private files and
    cross-tenant lookups return 404. Sends an ETag and long-lived Cache-Control
    so browsers/CDNs can cache immutable, key-versioned URLs safely.
    """
    record, path = open_public_file(session, file_id, company_id=company_id)
    etag = f'"{record.id}-{record.size_bytes}"'
    headers = {"ETag": etag, "Cache-Control": MEDIA_CACHE_CONTROL}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path=path, media_type=record.content_type, headers=headers)

# ---- store info (public bootstrap: resolves the shop by slug) ----
@router.get("/store/{slug}")
def store_info(slug: str, session: Session = Depends(get_db)):
    return svc.store_info(session, slug)


@router.get("/payment-methods")
def payment_methods(
    pincode: str | None = None,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.payment_methods(session, ctx.company_id, pincode=pincode)


# ---- shopper addresses ----
class AddressIn(BaseModel):
    label: str = Field(default="Home", max_length=40)
    name: str = Field(default="", max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    line1: str = Field(default="", max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=12)
    country: str = Field(default="IN", max_length=2)
    is_default: bool = False
    notes: str | None = None


@router.get("/addresses")
def list_addresses(
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    owner = svc.owner_key(ctx.user_id, ctx.anon_id)
    return svc.list_addresses(session, ctx.company_id, owner)


@router.post("/addresses")
def create_address(
    payload: AddressIn,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    owner = svc.owner_key(ctx.user_id, ctx.anon_id)
    return svc.save_address(session, ctx.company_id, owner, payload.model_dump())


@router.put("/addresses/{address_id}")
def update_address(
    address_id: str,
    payload: AddressIn,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    owner = svc.owner_key(ctx.user_id, ctx.anon_id)
    return svc.save_address(session, ctx.company_id, owner, payload.model_dump(), address_id)


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: str,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    owner = svc.owner_key(ctx.user_id, ctx.anon_id)
    svc.delete_address(session, ctx.company_id, owner, address_id)
    return {"deleted": address_id}


# ---- checkout / payment ----
class CheckoutAddressIn(BaseModel):
    line1: str = Field(default="", max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=12)
    country: str = Field(default="IN", max_length=2)


class CheckoutIn(BaseModel):
    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: CheckoutAddressIn = Field(default_factory=CheckoutAddressIn)
    payment_method: str = Field(default="card", max_length=20)
    shipping_total: str = Field(default="0", max_length=20)
    notes: str | None = Field(default=None, max_length=500)


@router.post("/checkout")
def guest_checkout(
    payload: CheckoutIn,
    x_idempotency_key: str = Header(alias="Idempotency-Key"),
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.guest_checkout(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        payload=payload.model_dump(),
        idempotency_key=x_idempotency_key,
    )


@router.get("/orders")
def guest_orders(
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.guest_orders(session, ctx.company_id, token)


class PayIn(BaseModel):
    method: str = Field(default="card", max_length=20)


@router.post("/orders/{order_id}/pay")
def guest_pay_order(
    order_id: str,
    payload: PayIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.guest_pay_order(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        order_id=order_id,
        method=payload.method,
    )


# ---- Razorpay hosted checkout ----
@router.post("/orders/{order_id}/razorpay")
def create_razorpay_order(
    order_id: str,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Create (or reuse) the Razorpay order the browser opens Checkout with."""
    return svc.create_razorpay_order(
        session, company_id=ctx.company_id, cart_token=token, order_id=order_id
    )


class RazorpayVerifyIn(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=64)
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    razorpay_signature: str = Field(min_length=1, max_length=256)


@router.post("/orders/{order_id}/razorpay/verify")
def verify_razorpay_payment(
    order_id: str,
    payload: RazorpayVerifyIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Verify the Checkout signature, then mark the order paid + invoice it."""
    return svc.verify_razorpay_payment(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        order_id=order_id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )


@router.post("/payments/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
    session: Session = Depends(get_db),
):
    """Razorpay webhook (no store headers): verified against the raw body."""
    body = await request.body()
    return svc.handle_razorpay_webhook(session, raw_body=body, signature=x_razorpay_signature)


# ---- cancellation & returns ----
@router.post("/orders/{order_id}/cancel")
def guest_cancel_order(
    order_id: str,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Cancel an order: release stock (unpaid) or refund the captured payment."""
    return svc.guest_cancel_order(
        session, company_id=ctx.company_id, cart_token=token, order_id=order_id
    )


class ReturnLineIn(BaseModel):
    product_id: str
    qty: Decimal = Field(gt=0)


class ReturnIn(BaseModel):
    lines: list[ReturnLineIn]
    notes: str | None = Field(default=None, max_length=500)


@router.get("/orders/{order_id}/returns")
def guest_order_returns(
    order_id: str,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.guest_order_returns(
        session, company_id=ctx.company_id, cart_token=token, order_id=order_id
    )


@router.post("/orders/{order_id}/returns", status_code=201)
def guest_request_return(
    order_id: str,
    payload: ReturnIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Request a return for a delivered order (ERP approves and completes it)."""
    return svc.guest_request_return(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        order_id=order_id,
        lines=[line.model_dump() for line in payload.lines],
        notes=payload.notes,
    )
