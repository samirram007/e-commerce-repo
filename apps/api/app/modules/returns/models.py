"""Returns models: sales returns, purchase returns with stock disposition."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

RETURN_STATUSES = ["requested", "approved", "rejected", "completed", "cancelled"]
DISPOSITIONS = ["resalable", "damaged", "quarantined", "discarded"]


class SalesReturn(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "sales_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credit_note_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    refund_payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesReturnLine(Base, TimestampMixin):
    __tablename__ = "sales_return_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    return_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_line_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    disposition: Mapped[str] = mapped_column(String(16), nullable=False, default="resalable")
    restock_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PurchaseReturn(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "purchase_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseReturnLine(Base, TimestampMixin):
    __tablename__ = "purchase_return_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    return_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_line_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
