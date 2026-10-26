"""Tax computation helpers — authoritative backend math only.

Line tax = round(taxable * percentage/100) using HALF_UP at currency precision.
The rounding rule is centralized here; every document uses the same helper so
frontend math can never disagree with the ledger.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.shared.money import dec, money


def compute_tax(taxable_base, percentage, *, precision: int = 2) -> Decimal:
    return money(dec(taxable_base) * dec(percentage) / Decimal("100"), precision)


def get_tax_rate(session: Session, company_id: str, tax_rate_id: str):
    from app.modules.taxes.models import TaxRate

    rate = session.get(TaxRate, tax_rate_id)
    if rate is None or rate.company_id != company_id or not rate.is_active:
        raise NotFoundError("Tax rate")
    return rate


def default_sales_tax_id(session: Session, company_id: str) -> str | None:
    from app.modules.taxes.models import TaxRate

    return session.scalar(
        select(TaxRate.id).where(
            TaxRate.company_id == company_id, TaxRate.is_default_sales.is_(True), TaxRate.is_active.is_(True)
        )
    )


def default_purchase_tax_id(session: Session, company_id: str) -> str | None:
    from app.modules.taxes.models import TaxRate

    return session.scalar(
        select(TaxRate.id).where(
            TaxRate.company_id == company_id, TaxRate.is_default_purchase.is_(True), TaxRate.is_active.is_(True)
        )
    )
