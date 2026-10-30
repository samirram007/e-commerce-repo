"""Invoicing models: customer invoices (snapshot-backed), lines, credit notes.

Posted invoices are immutable; corrections happen through credit notes that
reverse the stock/accounting effect and reference the original.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

INVOICE_STATUSES = ["draft", "posted", "cancelled"]
INVOICE_SOURCES = ["manual", "order"]


class CustomerInvoice(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "customer_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    # snapshot of commercial terms at issue time (legally relevant)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # totals (doc currency)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reversed_by_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "doc_number", name="uq_invoices_company_doc"),)


class InvoiceLine(Base, TimestampMixin):
    __tablename__ = "invoice_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # snapshot fields (what the customer was actually sold/billed)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hsn_sac_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
    description_snapshot: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    line_number: Mapped[int] = mapped_column(Numeric(5, 0), nullable=False, default=1)


class CreditNote(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "credit_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="posted", index=True)
    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    stock_restocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # timestamp when the returned stock was received back, if applicable


class CreditNoteLine(Base, TimestampMixin):
    __tablename__ = "credit_note_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    credit_note_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    invoice_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
