"""Accounting models: chart of accounts and the general ledger.

JournalEntry/JournalLine are immutable once posted. Corrections happen through
reversal entries linked back to the original. Every line stores the document
currency amount plus the exchange rate and company-currency (base) amount used
for ledger arithmetic.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class Account(Base, TimestampMixin):
    """Ledger account in the company chart of accounts."""
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # account group/type: asset | liability | equity | income | expense
    account_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    normal_side: Mapped[str] = mapped_column(String(8), nullable=False, default="debit")
    is_cash_or_bank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),)


class JournalEntry(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fiscal_year_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="posted", index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reversal_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))


class JournalLine(Base, TimestampMixin):
    __tablename__ = "journal_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entry_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # debit | credit
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)  # company base currency
    doc_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # subledger references for AR/AP: source document identifier
    party_ref: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    line_number: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False, default=0)
