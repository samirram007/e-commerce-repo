"""Company module: companies, currencies, exchange rates."""
from datetime import date

from sqlalchemy import Boolean, Date, Numeric, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class Currency(Base, TimestampMixin):
    """Supported currencies and their display precision."""
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    precision: Mapped[int] = mapped_column(Numeric(1, 0), nullable=False, default=2)


class CompanyAddress(Base, TimestampMixin):
    """Address record for a company (billing, shipping, warehouse, etc.)."""
    __tablename__ = "company_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    address_type: Mapped[str] = mapped_column(String(32), nullable=False)
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    company: Mapped[Company] = relationship("Company", back_populates="addresses")


class Company(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-IN")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # posting/behavior settings
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_guest_checkout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # public storefront slug: /storefront/shop/store/{slug} resolves the store
    storefront_slug: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON map of default account codes used by posting rules, validated at setup
    default_account_codes: Mapped[str] = mapped_column(String(1000), nullable=False, default="{}")
    # relationship to address records; back_populates for ORM navigation
    addresses: Mapped[list[CompanyAddress]] = relationship("CompanyAddress", back_populates="company", cascade="all, delete-orphan")


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
