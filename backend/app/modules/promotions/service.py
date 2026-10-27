"""Coupon rules and discount math — authoritative, like every other price.

The cart preview and the placed order both ask this module what a code is worth,
so a shopper can never see one discount and be charged another. Validation is
strict when a code is *entered* (the shopper gets told exactly what is wrong) and
tolerant when a stored code is merely *priced* — a cart whose subtotal dropped
below the coupon minimum should still render, showing the code as no longer
applied instead of failing.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.shared.money import dec, money

from .models import Coupon, CouponRedemption


@dataclass(frozen=True)
class QuoteLine:
    """A cart/order line as the coupon sees it."""

    product_id: str
    category_id: str | None
    amount: Decimal  # qty × unit price, before any discount


@dataclass(frozen=True)
class CouponQuote:
    """What a code is worth on a set of lines right now."""

    code: str | None = None
    description: str | None = None
    discount_total: Decimal = Decimal("0")
    #: product id → discount allocated to that line
    line_discounts: dict[str, Decimal] = field(default_factory=dict)
    valid: bool = False
    #: machine code + human message explaining why a stored code is not applied
    reason: str | None = None
    message: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "description": self.description,
            "discount_total": str(money(self.discount_total)),
            "valid": self.valid,
            "reason": self.reason,
            "message": self.message,
        }


NONE = CouponQuote()


def normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def get_coupon(session: Session, company_id: str, code: str | None) -> Coupon | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    return session.scalar(
        select(Coupon).where(Coupon.company_id == company_id, Coupon.code == normalized)
    )


def redemptions(session: Session, coupon_id: str, *, customer_key: str | None = None) -> int:
    stmt = select(func.count()).select_from(CouponRedemption).where(
        CouponRedemption.coupon_id == coupon_id
    )
    if customer_key is not None:
        stmt = stmt.where(CouponRedemption.customer_key == customer_key)
    return session.scalar(stmt) or 0


def _eligible_lines(coupon: Coupon, lines: list[QuoteLine]) -> list[QuoteLine]:
    if coupon.scope == "product":
        return [line for line in lines if line.product_id == coupon.product_id]
    if coupon.scope == "category":
        return [
            line
            for line in lines
            if line.category_id and line.category_id == coupon.category_id
        ]
    return list(lines)


def eligible_amount(coupon: Coupon, lines: list[QuoteLine]) -> Decimal:
    return money(sum((dec(line.amount) for line in _eligible_lines(coupon, lines)), Decimal("0")))


def compute_discount(
    coupon: Coupon, lines: list[QuoteLine]
) -> tuple[Decimal, dict[str, Decimal]]:
    """The total discount and its per-line allocation (exact, no rounding drift)."""
    eligible = _eligible_lines(coupon, lines)
    base = sum((dec(line.amount) for line in eligible), Decimal("0"))
    if base <= 0:
        return Decimal("0"), {}

    if coupon.kind == "fixed":
        total = min(dec(coupon.value), base)
    else:
        total = money(base * dec(coupon.value) / Decimal("100"))
        if coupon.max_discount is not None:
            total = min(total, dec(coupon.max_discount))
    total = money(max(total, Decimal("0")))
    if total <= 0:
        return Decimal("0"), {}

    # Spread proportionally; the last line absorbs the rounding remainder so the
    # allocation always adds back to the total to the paisa.
    allocations: dict[str, Decimal] = {}
    remaining = total
    for index, line in enumerate(eligible):
        share = remaining if index == len(eligible) - 1 else money(total * dec(line.amount) / base)
        share = min(share, money(dec(line.amount)))
        allocations[line.product_id] = allocations.get(line.product_id, Decimal("0")) + share
        remaining -= share
    return total, allocations


def _usable(
    session: Session, coupon: Coupon, lines: list[QuoteLine], *, customer_key: str | None
) -> tuple[str | None, str | None]:
    """(reason, message) for why the coupon cannot be used — (None, None) when it can."""
    now = datetime.now(timezone.utc)
    starts_at = coupon.starts_at
    if starts_at is not None and _aware(starts_at) > now:
        return "COUPON_NOT_STARTED", f"This code is not active until {starts_at:%d %b %Y}"
    ends_at = coupon.ends_at
    if ends_at is not None and _aware(ends_at) < now:
        return "COUPON_EXPIRED", "This code has expired"
    if not coupon.is_active:
        return "COUPON_INACTIVE", "This code is no longer available"
    if coupon.scope != "order" and not _eligible_lines(coupon, lines):
        what = "product" if coupon.scope == "product" else "category"
        return "COUPON_NOT_APPLICABLE", f"This code only applies to a specific {what}"
    if coupon.min_subtotal and eligible_amount(coupon, lines) < dec(coupon.min_subtotal):
        return (
            "COUPON_MIN_SUBTOTAL",
            f"Spend at least {money(dec(coupon.min_subtotal))} to use this code",
        )
    if coupon.max_redemptions is not None and redemptions(session, coupon.id) >= coupon.max_redemptions:
        return "COUPON_USAGE_LIMIT", "This code has reached its redemption limit"
    if (
        coupon.max_per_customer is not None
        and customer_key
        and redemptions(session, coupon.id, customer_key=customer_key) >= coupon.max_per_customer
    ):
        return "COUPON_ALREADY_USED", "You have already used this code"
    return None, None


def _aware(value: datetime) -> datetime:
    """Compare against now() even when a backend hands back a naive timestamp."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def price(
    session: Session,
    company_id: str,
    code: str | None,
    lines: list[QuoteLine],
    *,
    customer_key: str | None = None,
    strict: bool = False,
) -> CouponQuote:
    """What `code` is worth on `lines`.

    `strict` is for a code the shopper just entered: it raises `BusinessRuleError`
    with the exact reason. Otherwise an unusable code simply costs nothing, so a
    stored code never breaks a cart that no longer qualifies for it.
    """
    normalized = normalize_code(code)
    if not normalized:
        # No code at all is not an error, in either mode — only an unusable one is.
        return NONE
    coupon = get_coupon(session, company_id, normalized)
    if coupon is None:
        if strict:
            raise BusinessRuleError("COUPON_NOT_FOUND", "This code is not valid")
        return CouponQuote(code=normalized, reason="COUPON_NOT_FOUND", message="This code is not valid")
    reason, message = _usable(session, coupon, lines, customer_key=customer_key)
    if reason:
        if strict:
            raise BusinessRuleError(reason, message or "This code cannot be used")
        return CouponQuote(code=normalized, description=coupon.description, reason=reason, message=message)
    total, allocations = compute_discount(coupon, lines)
    if total <= 0 and strict:
        raise BusinessRuleError("COUPON_NO_DISCOUNT", "This code does not reduce this order")
    return CouponQuote(
        code=coupon.code,
        description=coupon.description,
        discount_total=total,
        line_discounts=allocations,
        valid=True,
    )


def redeem(
    session: Session,
    *,
    coupon: Coupon,
    order_id: str,
    amount: Decimal,
    customer_key: str | None = None,
) -> CouponRedemption:
    """Record that an order used the code (this is what the limits count)."""
    row = CouponRedemption(
        company_id=coupon.company_id,
        coupon_id=coupon.id,
        order_id=order_id,
        code=coupon.code,
        customer_key=customer_key or None,
        amount=money(amount),
    )
    session.add(row)
    session.flush()
    return row


def redeemed_amount(session: Session, coupon_id: str) -> Decimal:
    return money(
        session.scalar(
            select(func.coalesce(func.sum(CouponRedemption.amount), 0)).where(
                CouponRedemption.coupon_id == coupon_id
            )
        )
        or 0
    )
