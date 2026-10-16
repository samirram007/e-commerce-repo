"""Tax rate HTTP routes."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import P_COMPANY_SETTINGS
from app.db.unit_of_work import get_db
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.taxes.models import TaxRate

router = APIRouter(prefix="/taxes")


class TaxRateIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    percentage: Decimal = Field(ge=0, le=100)
    is_default_sales: bool = False
    is_default_purchase: bool = False


class TaxRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    percentage: Decimal
    is_default_sales: bool
    is_default_purchase: bool
    is_active: bool


@router.get("", response_model=list[TaxRateOut])
def list_taxes(ctx: CompanyCtx = Depends(guard(P_COMPANY_SETTINGS)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(TaxRate).where(TaxRate.company_id == ctx.company_id).order_by(TaxRate.code)
    ).scalars().all()
    return [TaxRateOut.model_validate(r) for r in rows]


@router.post("", response_model=TaxRateOut, status_code=201)
def create_tax(
    payload: TaxRateIn, ctx: CompanyCtx = Depends(guard(P_COMPANY_SETTINGS)), session: Session = Depends(get_db)
):
    if payload.is_default_sales:
        for row in session.execute(select(TaxRate).where(TaxRate.company_id == ctx.company_id, TaxRate.is_default_sales.is_(True))).scalars():
            row.is_default_sales = False
    if payload.is_default_purchase:
        for row in session.execute(select(TaxRate).where(TaxRate.company_id == ctx.company_id, TaxRate.is_default_purchase.is_(True))).scalars():
            row.is_default_purchase = False
    tax = TaxRate(
        company_id=ctx.company_id,
        code=payload.code,
        name=payload.name,
        percentage=payload.percentage,
        is_default_sales=payload.is_default_sales,
        is_default_purchase=payload.is_default_purchase,
        created_by=ctx.user.id,
    )
    session.add(tax)
    session.flush()
    return TaxRateOut.model_validate(tax)
