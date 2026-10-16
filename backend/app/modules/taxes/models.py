"""Tax rates reference data."""
from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class TaxRate(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "tax_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # percentage, e.g. 15.00 for 15%
    percentage: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    is_default_sales: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = tuple()
