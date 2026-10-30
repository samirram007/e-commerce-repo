"""Carrier profiles: one company's configuration for a shipping carrier.

Third-party carriers (Shiprocket, Delhivery, BlueDart, DTDC, FedEx, DHL) and the
merchant's own dispatch are configured per company here: which ones are enabled,
in what order they are offered at checkout, and the credentials the dispatch and
rate adapters use. Credentials are write-only — the API returns only the names of
the keys that are set.
"""
from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class CarrierProfile(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "carrier_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    carrier: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    credentials: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    settings: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "carrier", name="uq_carrier_profile_company_carrier"),)
