"""Storage locations: warehouse hierarchy (zone/aisle/rack/bin via type + parent)."""
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

LOCATION_TYPES = ["warehouse", "zone", "aisle", "rack", "bin"]


class StorageLocation(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "storage_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("storage_locations.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_type: Mapped[str] = mapped_column(String(16), nullable=False, default="warehouse", index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_storage_locations_company_code"),)
