"""Storefront HTTP routes — public (no auth required) shopping surface.

Every route needs an `X-Company-Id` header (which company's store this is) but
NOT a bearer token: guests browse, favorite and fill a token cart; checkout
still requires a signed-in customer (existing /storefront/checkout).
"""
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, BusinessRuleError, NotFoundError
from app.core.security import decode_token
from app.db.unit_of_work import commit_before_reply, get_db
from app.modules.catalog.models import Product
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


class CouponCodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


@router.post("/cart/coupon")
def guest_cart_coupon(
    payload: CouponCodeIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Apply a promo code to the guest cart (validated server-side)."""
    return svc.apply_coupon(session, ctx.company_id, token, payload.code)


@router.delete("/cart/coupon")
def guest_cart_coupon_clear(
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Remove the applied code; the cart is quoted at full price again."""
    return svc.clear_coupon(session, ctx.company_id, token)


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


# ---- shopper uploads (documents/photos the customer sends the store) ----
@router.get("/uploads")
def list_shopper_uploads(ctx: StoreCtx = Depends(store_ctx), session: Session = Depends(get_db)):
    """Whether uploads are open, and what this shopper has already sent."""
    return {
        "enabled": svc.shopper_uploads_enabled(session, ctx.company_id),
        "items": svc.shopper_upload_list(
            session, company_id=ctx.company_id, user_id=ctx.user_id, anon_id=ctx.anon_id
        ),
    }


@router.post("/uploads", status_code=201)
def create_shopper_upload(
    file: UploadFile,
    order_id: str | None = Form(default=None),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Send a file to the store (colour proof, prescription, return photo...)."""
    return svc.upload_shopper_file(
        session,
        company_id=ctx.company_id,
        user_id=ctx.user_id,
        anon_id=ctx.anon_id,
        file=file,
        order_id=order_id,
    )


@router.get("/uploads/{file_id}")
def download_shopper_upload(
    file_id: str,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Download one of the shopper's own uploads (never anybody else's)."""
    record, path, content_type = svc.shopper_file_contents(
        session,
        company_id=ctx.company_id,
        user_id=ctx.user_id,
        anon_id=ctx.anon_id,
        file_id=file_id,
    )
    return FileResponse(path=path, media_type=content_type, filename=record.original_name)


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


class ShopperRegisterIn(BaseModel):
    """Public signup: the store is resolved by slug, the shopper gets no ERP roles."""

    slug: str = Field(default="default", max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=200)


@router.post("/register", status_code=201)
def register_shopper(payload: ShopperRegisterIn, session: Session = Depends(get_db)):
    return svc.register_shopper(
        session,
        slug=payload.slug,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )


@router.get("/payment-methods")
def payment_methods(
    pincode: str | None = None,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    return svc.payment_methods(session, ctx.company_id, pincode=pincode)


@router.get("/shipping-options")
def shipping_options(
    pincode: str | None = None,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Delivery options the shop configured, priced for the current cart."""
    return svc.shipping_options_for_cart(
        session, company_id=ctx.company_id, cart_token=token, pincode=pincode
    )


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
    shipping_carrier: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=500)


@router.post("/checkout")
def guest_checkout(
    payload: CheckoutIn,
    x_idempotency_key: str = Header(alias="Idempotency-Key"),
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    result = svc.guest_checkout(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        payload=payload.model_dump(),
        idempotency_key=x_idempotency_key,
    )
    # The browser asks for the Razorpay order that reads this row as soon as it
    # has the reply (`POST /orders/{id}/razorpay`). Commit before replying so the
    # follow-up can never hit a connection that does not see the order yet.
    commit_before_reply(session)
    return result


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


# ---- purchase feedback ----
class ReviewIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, max_length=4000)


class OrderFeedbackIn(BaseModel):
    delivery_rating: int | None = Field(default=None, ge=1, le=5)
    packaging_rating: int | None = Field(default=None, ge=1, le=5)
    service_rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


def _shopper_owner(ctx: StoreCtx) -> str | None:
    """Identity of the shopper writing feedback, when we know it."""
    if not ctx.user_id and not ctx.anon_id:
        return None
    return svc.owner_key(ctx.user_id, ctx.anon_id)


@router.get("/orders/{order_id}/feedback")
def order_feedback(
    order_id: str,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """What may still be reviewed on this order, plus what was already sent."""
    return svc.order_feedback_state(session, company_id=ctx.company_id, cart_token=token, order_id=order_id)


@router.post("/orders/{order_id}/reviews", status_code=201)
def create_review(
    order_id: str,
    payload: ReviewIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Review one purchased item (published once the store approves it)."""
    return svc.submit_product_review(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        order_id=order_id,
        product_id=payload.product_id,
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
        owner=_shopper_owner(ctx),
    )


@router.post("/orders/{order_id}/feedback", status_code=201)
def create_order_feedback(
    order_id: str,
    payload: OrderFeedbackIn,
    token: str = Depends(cart_token_header),
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Rate the delivery, the packaging and the service for this order."""
    return svc.submit_order_experience(
        session,
        company_id=ctx.company_id,
        cart_token=token,
        order_id=order_id,
        delivery_rating=payload.delivery_rating,
        packaging_rating=payload.packaging_rating,
        service_rating=payload.service_rating,
        comment=payload.comment,
        owner=_shopper_owner(ctx),
    )


@router.get("/products/{product_id}/reviews")
def product_reviews(
    product_id: str,
    ctx: StoreCtx = Depends(store_ctx),
    session: Session = Depends(get_db),
):
    """Published reviews and the star summary for one product."""
    return svc.product_reviews(session, ctx.company_id, product_id)


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
