"""Storefront module models — interests and delivery zones live beside the
catalog tables (same domain) and are re-exported here for clean imports, plus
the shopper's saved address book and the public shop's marketing content.
"""
from decimal import Decimal

from sqlalchemy import Boolean, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin
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


# ---- public storefront content (company-scoped, admin-managed) ----


class StorefrontHeroSlide(Base, TimestampMixin, CreatedByMixin):
    """One slide of the public shop's home-page hero carousel."""

    __tablename__ = "storefront_hero_slides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    eyebrow: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    cta: Mapped[str] = mapped_column(String(80), nullable=False, default="Shop now")
    category_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tone: Mapped[str] = mapped_column(String(16), nullable=False, default="indigo")
    image_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")


class StorefrontTestimonial(Base, TimestampMixin, CreatedByMixin):
    """A customer quote shown on the home page."""

    __tablename__ = "storefront_testimonials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")


class StorefrontFaq(Base, TimestampMixin, CreatedByMixin):
    """One FAQ entry; `group_name` supplies the grouping on the help page.

    A flat table (rather than group→item tables) keeps the admin CRUD trivial
    and matches how the data is rendered: a flat list grouped client-side.
    """

    __tablename__ = "storefront_faqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    question: Mapped[str] = mapped_column(String(300), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")


class StorefrontPolicy(Base, TimestampMixin, CreatedByMixin):
    """A legal/info page (shipping, returns, privacy, terms).

    `updated` is a display string (e.g. "October 2026") because policy text is
    revised monthly at best — storing a full date would imply a precision the
    content does not have.
    """

    __tablename__ = "storefront_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    updated: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[{heading, body}]
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    __table_args__ = (UniqueConstraint("company_id", "slug", name="uq_storefront_policies_slug"),)


class StorefrontSettings(Base, TimestampMixin, CreatedByMixin):
    """Per-store settings driving shipping rules, contact info and site copy.

    One row per company. Money fields are typed columns; the decorative lists
    (announcements, perks, about blocks) are JSON so adding one does not need a
    migration — they are rendered verbatim, never computed from.
    """

    __tablename__ = "storefront_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # shipping rules (None = rule disabled → shipping is free)
    free_shipping_threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    flat_shipping_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    #: How many days after delivery a shopper may request a return (0 = no limit).
    return_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")
    # contact block
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    map_image_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # marketing copy lists (JSON)
    announcements: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[str]
    perks: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[{icon,title,text}]
    about_values: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[{title,text}]
    about_stats: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[{value,label}]
    footer_about: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (UniqueConstraint("company_id", name="uq_storefront_settings_company"),)
