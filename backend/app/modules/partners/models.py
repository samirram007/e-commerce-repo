"""Partners models: customers, vendors, addresses, credit terms."""
from decimal import Decimal

from sqlalchemy import Boolean, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class Customer(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(Numeric(5, 0), nullable=False, default=0)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    # user account linking optional storefront logins
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_customers_company_code"),)


class Vendor(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(Numeric(5, 0), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_vendors_company_code"),)


class PartnerAddress(Base, TimestampMixin):
    """Snapshot-ready address book for customers and vendors."""
    __tablename__ = "partner_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    partner_type: Mapped[str] = mapped_column(String(10), nullable=False)  # customer|vendor
    partner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    address_type: Mapped[str] = mapped_column(String(16), nullable=False, default="billing")  # billing|shipping
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
