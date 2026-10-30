"""Purchase feedback models: product reviews and order-experience feedback.

A product review is tied to the purchase that earned it (`order_id` +
`product_id` are unique), starts as `pending` and only reaches the storefront
once the store approves it. Approved ratings are aggregated onto the product's
`rating_avg`/`rating_count`, which the catalog already exposes.

Order feedback is private to the store: how the delivery, the packaging and the
service were rated for one order, at most once per order.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

REVIEW_STATUSES = ["pending", "approved", "rejected"]

#: A rating is a whole number of stars.
MIN_RATING = 1
MAX_RATING = 5


class ProductReview(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    #: Shopper identity that wrote it (`user:<id>` or `anon:<id>`).
    owner_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending", index=True)
    moderation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_product_review_order_product"),
    )


class OrderFeedback(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "order_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    owner_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    delivery_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packaging_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("order_id", name="uq_order_feedback_order"),)
