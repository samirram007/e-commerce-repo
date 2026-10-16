"""Inventory models: immutable stock ledger, on-hand balances, counts.

Posted movement rows are never updated or deleted; corrections are made by
posting compensating movements (adjustment/reversal) that reference the source.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

MOVEMENT_TYPES = [
    "receipt", "issue", "transfer_out", "transfer_in", "adjustment",
    "reserve", "release", "return_receipt", "count", "opening",
]


class StockLedgerEntry(Base, TimestampMixin, CreatedByMixin):
    """One immutable stock movement. qty_delta signed; unit_cost present for
    receipts/issues (weighted-average)."""
    __tablename__ = "stock_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    batch_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # source linkage
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    counter_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = tuple()


class StockOnHand(Base, TimestampMixin):
    """Live balance per company/product/location (+batch). Updated only inside
    the same transaction as the ledger row it mirrors."""
    __tablename__ = "stock_on_hand"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    reserved: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))

    __table_args__ = (
        UniqueConstraint("company_id", "product_id", "location_id", "batch_ref", name="uq_stock_on_hand_key"),
    )


class ProductValuation(Base, TimestampMixin):
    """Weighted-average cost per company/product (base currency)."""
    __tablename__ = "product_valuations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))

    __table_args__ = (UniqueConstraint("company_id", "product_id", name="uq_valuation_product"),)


class StockCount(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "stock_counts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)  # open|posted|cancelled
    # Keep line details in JSON (small counts); production systems would use a child table.
    lines: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class StockCountLine(Base, TimestampMixin):
    __tablename__ = "stock_count_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    count_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    counted_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    system_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    variance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))


class StockTransfer(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "stock_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="done", index=True)
    transfer_ref: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    lines: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    in_transit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
