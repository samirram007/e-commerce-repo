"""Coupons: promotional codes a company issues and customers redeem.

A coupon is a percentage or a fixed amount off, optionally capped, with a
minimum eligible subtotal, an applicability (the whole order, one category or one
product), an active window and redemption limits. `CouponRedemption` is the audit
trail — one row per order that used the code — and is what enforces the limits.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

#: How the coupon is valued: a percentage of the eligible subtotal, or a fixed
#: amount off it.
COUPON_KINDS = ["percent", "fixed"]
#: Which lines the coupon applies to.
COUPON_SCOPES = ["order", "category", "product"]


class Coupon(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    #: Stored upper-cased; lookups are case-insensitive for the shopper.
    code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: one of COUPON_KINDS
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="percent")
    #: percentage (0–100) when `kind` is percent, otherwise an amount in the
    #: company's base currency
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    #: ceiling for a percentage coupon; null means uncapped
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    #: smallest eligible subtotal the coupon may be used on
    min_subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    #: one of COUPON_SCOPES
    scope: Mapped[str] = mapped_column(String(10), nullable=False, default="order")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: redemptions allowed across all customers (null = unlimited)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: redemptions allowed per customer (null = unlimited)
    max_per_customer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = tuple()


class CouponRedemption(Base, TimestampMixin):
    """One order that used a code, with the amount it took off."""

    __tablename__ = "coupon_redemptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    coupon_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    #: who used it (user id, else the checkout e-mail) for per-customer limits
    customer_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
