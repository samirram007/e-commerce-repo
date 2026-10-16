"""Payments module: provider payment records (mock by default), receipts and
payment vouchers with allocations to invoices/bills."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

PAYMENT_DIRECTIONS = ["receipt", "payment"]  # receipt: money in; payment: money out


class PaymentRecord(Base, TimestampMixin, CreatedByMixin):
    """A payment execution against the provider (mock) or a manual records."""
    __tablename__ = "payment_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="mock_gateway")  # mock_gateway|cash|bank|card
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    provider_ref: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="succeeded", index=True)  # pending|succeeded|failed|refunded
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    amount_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    # linkage
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    vendor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("provider", "provider_ref", name="uq_payment_provider_ref"),)


class PaymentAllocation(Base, TimestampMixin):
    """Allocation of a paid amount to a document; keeps allocations unique."""
    __tablename__ = "payment_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(24), nullable=False)  # invoice|credit_note|vendor_bill|sales_return
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("payment_id", "document_id", name="uq_payment_allocation_pair"),)
