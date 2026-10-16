"""Fulfillment models: shipments, shipment lines, tracking events, PODs."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

SHIPMENT_STATUSES = ["created", "picking", "picked", "packed", "dispatched", "in_transit", "delivered", "failed", "returned_to_origin"]


class Shipment(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created", index=True)
    carrier_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    shipping_address_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    picked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    packed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pod_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # carrier webhook secret is stored on the carrier profile (delivery module)


class ShipmentLine(Base, TimestampMixin):
    __tablename__ = "shipment_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_line_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
