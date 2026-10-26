"""Catalog models: categories, units of measure, products, price lists,
plus storefront interest (favorites/watchlist)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

#: Badge values a product can carry on the storefront (New/Sale/Bestseller/Limited).
PRODUCT_BADGES = ("New", "Sale", "Bestseller", "Limited")


class Category(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # storefront presentation fields (public shop renders from these)
    slug: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    blurb: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    image_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    __table_args__ = (UniqueConstraint("company_id", "slug", name="uq_categories_company_slug"),)


class UnitOfMeasure(Base, TimestampMixin):
    __tablename__ = "units_of_measure"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_uom_company_code"),)


class UnitConversion(Base, TimestampMixin):
    """Explicit, validated conversion rule between two UoMs; never implied."""
    __tablename__ = "unit_conversions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_uom_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_uom_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    __table_args__ = (UniqueConstraint("company_id", "from_uom_id", "to_uom_id", name="uq_unit_conversion_pair"),)


class Product(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    uom_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("units_of_measure.id"), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # HSN (goods) or SAC (services) code printed on GST invoices
    hsn_sac: Mapped[str | None] = mapped_column(String(12), nullable=True)
    # stock_type: stock | service | non_inventory
    stock_type: Mapped[str] = mapped_column(String(16), nullable=False, default="stock")
    track_batches: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    track_serials: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # base selling/cost prices (default price list rows may override by date)
    base_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    base_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    default_tax_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    image_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_sellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_purchasable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # storefront counters (monotonic; drives the "trending" rail)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # ---- storefront presentation fields ----
    # `base_price` stays the selling price; `compare_at_price` is the optional
    # pre-discount anchor used to compute the discount server-side.
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(16), nullable=True)  # New|Sale|Bestseller|Limited
    highlights: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[str]
    colors: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[str] (hex swatches)
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),
        UniqueConstraint("company_id", "slug", name="uq_products_company_slug"),
    )


class ProductImage(Base, TimestampMixin, CreatedByMixin):
    """A gallery photo for a product.

    `Product.image_file_id` remains the single cover/primary image (kept so
    existing admin flows and rows keep working); `ProductImage` rows are the
    ordered gallery and always include the cover as their first row when one is
    set through the storefront admin.
    """

    __tablename__ = "product_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alt: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PriceList(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "price_lists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PriceListItem(Base, TimestampMixin):
    """Price rows with an effective date range. When multiple rows apply,
    the row with the latest effective_from wins."""
    __tablename__ = "price_list_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    price_list_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProductInterest(Base, TimestampMixin):
    """Shopper's saved products: favorites and watchlist.

    One row per (kind, product, owner). The owner is the signed-in user when
    available, otherwise the browser's anonymous id (X-Anon-Id header) so guest
    browsing works without an account; favorites migrate server-side when the
    anonymous id is claimed at checkout/login time.
    """

    __tablename__ = "product_interests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # favorite | watchlist
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    anon_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class DeliveryZone(Base, TimestampMixin, CreatedByMixin):
    """Pincode → deliverability per company; seed emptily and admin-managed."""

    __tablename__ = "delivery_zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pincode: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    deliverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    eta_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cod_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("company_id", "pincode", name="uq_delivery_zones_pin"),)
