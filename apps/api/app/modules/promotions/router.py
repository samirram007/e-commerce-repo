"""Coupon HTTP routes — the company's coupon admin surface.

Codes live per company and are priced by `service.py`; this router only stores
and lists them, so a coupon created here is immediately usable at checkout.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.permissions import P_PROMOTIONS_MANAGE, P_PROMOTIONS_VIEW
from app.db.unit_of_work import get_db
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.promotions import service as promotions
from app.modules.promotions.models import Coupon
from app.shared.pagination import ListParams, Page, apply_list, paginate

router = APIRouter(prefix="/promotions")

KIND_PATTERN = "^(percent|fixed)$"
SCOPE_PATTERN = "^(order|category|product)$"


class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=200)
    kind: str = Field(default="percent", pattern=KIND_PATTERN)
    value: Decimal = Field(gt=0)
    max_discount: Decimal | None = Field(default=None, ge=0)
    min_subtotal: Decimal = Field(default=Decimal("0"), ge=0)
    scope: str = Field(default="order", pattern=SCOPE_PATTERN)
    category_id: str | None = None
    product_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    max_per_customer: int | None = Field(default=None, ge=1)
    is_active: bool = True


class CouponPatch(BaseModel):
    """PATCH body — only the fields present are changed."""

    description: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, pattern=KIND_PATTERN)
    value: Decimal | None = Field(default=None, gt=0)
    max_discount: Decimal | None = Field(default=None, ge=0)
    min_subtotal: Decimal | None = Field(default=None, ge=0)
    scope: str | None = Field(default=None, pattern=SCOPE_PATTERN)
    category_id: str | None = None
    product_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    max_per_customer: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    description: str | None
    kind: str
    value: Decimal
    max_discount: Decimal | None
    min_subtotal: Decimal
    scope: str
    category_id: str | None
    product_id: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    max_redemptions: int | None
    max_per_customer: int | None
    is_active: bool
    #: lifetime usage, which is what the limits are checked against
    redemptions: int = 0
    redeemed_amount: Decimal = Decimal("0")


def _check_shape(
    *, kind: str, scope: str, value: Decimal, category_id: str | None,
    product_id: str | None, starts_at: datetime | None, ends_at: datetime | None,
) -> None:
    if kind == "percent" and value > 100:
        raise BusinessRuleError("COUPON_BAD_VALUE", "A percentage coupon cannot exceed 100%")
    if scope == "category" and not category_id:
        raise BusinessRuleError("COUPON_BAD_SCOPE", "Pick the category this coupon applies to")
    if scope == "product" and not product_id:
        raise BusinessRuleError("COUPON_BAD_SCOPE", "Pick the product this coupon applies to")
    if starts_at and ends_at and ends_at <= starts_at:
        raise BusinessRuleError("COUPON_BAD_WINDOW", "The end date must come after the start date")


def _out(session: Session, coupon: Coupon) -> CouponOut:
    return CouponOut.model_validate(coupon).model_copy(
        update={
            "redemptions": promotions.redemptions(session, coupon.id),
            "redeemed_amount": promotions.redeemed_amount(session, coupon.id),
        }
    )


def _get(session: Session, company_id: str, coupon_id: str) -> Coupon:
    coupon = session.get(Coupon, coupon_id)
    if coupon is None or coupon.company_id != company_id:
        raise NotFoundError("Coupon")
    return coupon


def _code_is_free(session: Session, company_id: str, code: str, *, coupon_id: str | None = None) -> None:
    existing = promotions.get_coupon(session, company_id, code)
    if existing is not None and existing.id != coupon_id:
        raise ConflictError("COUPON_CODE_TAKEN", f"Code {existing.code} already exists")


@router.get("", response_model=Page[CouponOut])
def list_coupons(
    params: ListParams = Depends(),
    ctx: CompanyCtx = Depends(guard(P_PROMOTIONS_VIEW)),
    session: Session = Depends(get_db),
):
    """Server-side list: search, sort and pagination like every other screen."""
    query = apply_list(
        select(Coupon).where(Coupon.company_id == ctx.company_id),
        Coupon,
        params,
        search_fields=("code", "description"),
        sortable_fields=(
            "code", "kind", "value", "min_subtotal", "is_active", "created_at", "updated_at",
        ),
        default_sort=("code", False),
    )
    rows, total = paginate(session, query, params)
    return Page[CouponOut](
        items=[_out(session, row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(
    payload: CouponIn,
    ctx: CompanyCtx = Depends(guard(P_PROMOTIONS_MANAGE)),
    session: Session = Depends(get_db),
):
    _check_shape(
        kind=payload.kind,
        scope=payload.scope,
        value=payload.value,
        category_id=payload.category_id,
        product_id=payload.product_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    _code_is_free(session, ctx.company_id, payload.code)
    coupon = Coupon(
        company_id=ctx.company_id,
        code=promotions.normalize_code(payload.code),
        description=payload.description,
        kind=payload.kind,
        value=payload.value,
        max_discount=payload.max_discount,
        min_subtotal=payload.min_subtotal,
        scope=payload.scope,
        category_id=payload.category_id if payload.scope == "category" else None,
        product_id=payload.product_id if payload.scope == "product" else None,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        max_redemptions=payload.max_redemptions,
        max_per_customer=payload.max_per_customer,
        is_active=payload.is_active,
        created_by=ctx.user.id,
    )
    session.add(coupon)
    session.flush()
    return _out(session, coupon)


@router.patch("/{coupon_id}", response_model=CouponOut)
def update_coupon(
    coupon_id: str,
    payload: CouponPatch,
    ctx: CompanyCtx = Depends(guard(P_PROMOTIONS_MANAGE)),
    session: Session = Depends(get_db),
):
    coupon = _get(session, ctx.company_id, coupon_id)
    changes = payload.model_dump(exclude_unset=True)
    kind = changes.get("kind", coupon.kind)
    scope = changes.get("scope", coupon.scope)
    _check_shape(
        kind=kind,
        scope=scope,
        value=changes.get("value", coupon.value),
        category_id=changes.get("category_id", coupon.category_id),
        product_id=changes.get("product_id", coupon.product_id),
        starts_at=changes.get("starts_at", coupon.starts_at),
        ends_at=changes.get("ends_at", coupon.ends_at),
    )
    for field, value in changes.items():
        setattr(coupon, field, value)
    # A coupon only ever targets what its current scope needs.
    if coupon.scope != "category":
        coupon.category_id = None
    if coupon.scope != "product":
        coupon.product_id = None
    session.flush()
    return _out(session, coupon)


@router.delete("/{coupon_id}", response_model=CouponOut)
def deactivate_coupon(
    coupon_id: str,
    ctx: CompanyCtx = Depends(guard(P_PROMOTIONS_MANAGE)),
    session: Session = Depends(get_db),
):
    """Stop a code from being usable without erasing its redemption history."""
    coupon = _get(session, ctx.company_id, coupon_id)
    coupon.is_active = False
    session.flush()
    return _out(session, coupon)


@router.get("/{coupon_id}/redemptions")
def list_redemptions(
    coupon_id: str,
    ctx: CompanyCtx = Depends(guard(P_PROMOTIONS_VIEW)),
    session: Session = Depends(get_db),
):
    """Who used the code, on which order, for how much."""
    from app.modules.promotions.models import CouponRedemption

    _get(session, ctx.company_id, coupon_id)
    rows = session.execute(
        select(CouponRedemption)
        .where(CouponRedemption.coupon_id == coupon_id)
        .order_by(CouponRedemption.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "code": row.code,
            "customer_key": row.customer_key,
            "amount": str(row.amount),
            "redeemed_at": row.created_at.astimezone(timezone.utc).isoformat() if row.created_at else None,
        }
        for row in rows
    ]
