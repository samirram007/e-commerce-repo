"""Company module: companies, currencies, exchange rates."""
from datetime import date

from sqlalchemy import Boolean, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class Currency(Base, TimestampMixin):
    """Supported currencies and their display precision."""
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    precision: Mapped[int] = mapped_column(Numeric(1, 0), nullable=False, default=2)


class Company(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-US")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # posting/behavior settings
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_guest_checkout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON map of default account codes used by posting rules, validated at setup
    default_account_codes: Mapped[str] = mapped_column(String(1000), nullable=False, default="{}")


class ExchangeRate(Base, TimestampMixin, CreatedByMixin):
    """Rate to convert *from* one currency into the company base currency,
    effective per date. One row per company/currency/date."""
    __tablename__ = "exchange_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Numeric] = mapped_column(Numeric(18, 8), nullable=False)  # type: ignore[valid-type]

    __table_args__ = (UniqueConstraint("company_id", "from_currency", "to_currency", "rate_date", name="uq_exchange_rates_unique"),)
