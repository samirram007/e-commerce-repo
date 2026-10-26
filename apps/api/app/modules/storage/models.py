"""Storage locations: facility → zone → aisle → rack → shelf → bin hierarchy.

A location's `location_type` determines its rank. A child must have a strictly
greater rank than its parent, so a *facility* (rank 0) is always a root and only
a *stockable* leaf type can sit at the bottom and hold stock.
"""
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

# Ordered hierarchy. Multiple facility types are accepted so a company can name
# its root nodes the way it actually works (warehouse, godown, store, depot, …).
LOCATION_TYPE_RANKS: dict[str, int] = {
    # facilities / sites — may be a root (no parent)
    "warehouse": 0,
    "godown": 0,
    "store": 0,
    "depot": 0,
    "branch": 0,
    "showroom": 0,
    "outlet": 0,
    "yard": 0,
    "cold_storage": 0,
    "bonded": 0,
    "transit": 0,
    "quarantine": 0,
    "scrap": 0,
    # internal structure
    "floor": 1,
    "zone": 1,
    "aisle": 2,
    "rack": 3,
    "shelf": 4,
    "bin": 5,
}

# Every accepted type, ordered (facility types first).
LOCATION_TYPES: tuple[str, ...] = tuple(LOCATION_TYPE_RANKS)

# Facility types may be a root; every other type requires a parent.
FACILITY_TYPES: frozenset[str] = frozenset(
    name for name, rank in LOCATION_TYPE_RANKS.items() if rank == 0
)

# Types that may physically hold stock (stock movements / on-hand only allow these).
STOCKABLE_TYPES: frozenset[str] = frozenset({"bin"})


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
