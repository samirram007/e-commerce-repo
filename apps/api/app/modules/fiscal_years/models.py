"""Fiscal years and accounting periods."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class FiscalYear(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "fiscal_years"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "start_date", name="uq_fiscal_years_company_start"),)


class AccountingPeriod(Base, TimestampMixin):
    """Sub-period of a fiscal year (monthly by default). Posting into a closed
    period or outside any open period is rejected by the accounting service."""
    __tablename__ = "accounting_periods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fiscal_year_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
