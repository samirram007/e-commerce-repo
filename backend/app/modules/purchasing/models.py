"""Purchasing models: purchase orders, goods receipts, vendor bills."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

PO_STATUSES = ["draft", "submitted", "approved", "partially_received", "received", "closed", "cancelled"]
RECEIPT_STATUSES = ["posted"]
BILL_STATUSES = ["draft", "posted", "cancelled"]


class PurchaseOrder(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseOrderLine(Base, TimestampMixin):
    __tablename__ = "purchase_order_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    uom_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    line_number: Mapped[int] = mapped_column(Numeric(5, 0), nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoodsReceipt(Base, TimestampMixin, CreatedByMixin):
    """Receipt of goods; creates stock ledger receipts and updates PO lines."""
    __tablename__ = "goods_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted", index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)


class GoodsReceiptLine(Base, TimestampMixin):
    __tablename__ = "goods_receipt_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    receipt_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_line_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class VendorBill(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "vendor_bills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vendor_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    receipt_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted", index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class VendorBillLine(Base, TimestampMixin):
    __tablename__ = "vendor_bill_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    bill_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    receipt_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
