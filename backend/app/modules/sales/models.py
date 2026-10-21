"""Sales models: carts, orders, order lines. Stock reservations are managed in
the inventory module via ledger entries sourced from the order."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

ORDER_STATUSES = ["pending_payment", "paid", "confirmed", "fulfilling", "shipped", "delivered", "cancelled", "refunded"]
CART_STATUSES = ["open", "converted", "abandoned"]


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    updated_at_2: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cart_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_items_pair"),)


class SalesOrder(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "sales_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_payment", index=True)
    payment_state: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid", index=True)  # unpaid|paid|refunded|partial
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    # address snapshot at checkout
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    invoice_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customer_invoices.id"), nullable=True, index=True)
    cart_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderLine(Base, TimestampMixin):
    __tablename__ = "order_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description_snapshot: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    line_number: Mapped[int] = mapped_column(Numeric(5, 0), nullable=False, default=1)
    reserved_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
