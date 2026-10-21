"""Storefront module models — interests and delivery zones live beside the
catalog tables (same domain) and are re-exported here for clean imports, plus
the shopper's saved address book.
"""
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, TimestampMixin
from app.modules.catalog.models import DeliveryZone, ProductInterest  # noqa: F401


class StorefrontAddress(Base, TimestampMixin):
    """A saved delivery address for a shopper (guest or signed-in).

    `owner_key` identifies the shopper without a users table dependency:
    "user:<id>" for a signed-in account, "anon:<id>" for a browser guest.
    """

    __tablename__ = "storefront_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False, default="Home")
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line1: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
