"""Reports HTTP routes (permission-gated, company-scoped)."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import P_REPORTS_VIEW
from app.db.unit_of_work import get_db
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.payments.service import outstanding_for_document
from app.modules.reports import service as svc

router = APIRouter(prefix="/reports")


@router.get("/sales-summary")
def sales_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    return svc.sales_summary(session, ctx.company_id, from_date=from_date, to_date=to_date)


@router.get("/purchase-summary")
def purchase_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    return svc.purchase_summary(session, ctx.company_id, from_date=from_date, to_date=to_date)


@router.get("/delivery-performance")
def delivery_performance(
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    return svc.delivery_performance(session, ctx.company_id, from_date=None, to_date=None)


@router.get("/stock-valuation")
def stock_valuation(ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)), session: Session = Depends(get_db)):
    return svc.stock_valuation(session, ctx.company_id)
