"""Per-user period context: active fiscal year / accounting period / reporting period.

A *reporting period* is a user-defined named date range (private to its owner
within a company). The *period context* is the user's persisted selection of an
active fiscal year, accounting period and reporting period, stored one row per
(user, company).
"""
from datetime import date

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class ReportingPeriod(Base, TimestampMixin, CreatedByMixin):
    """A user-defined named date range used for reporting.

    Owned by a single user within a company (`user_id`), so it is never visible
    to other members. Names are unique per owner.
    """
    __tablename__ = "reporting_periods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "name", name="uq_reporting_periods_owner_name"),
    )


class UserPeriodPreference(Base, TimestampMixin):
    """The active fiscal year / accounting period / reporting period a user has
    selected for a company. Exactly one row per (user, company)."""
    __tablename__ = "user_period_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fiscal_year_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    accounting_period_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reporting_period_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_period_pref_pair"),
    )
