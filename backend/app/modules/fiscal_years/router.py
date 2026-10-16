"""Fiscal year HTTP routes."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_FISCAL_MANAGE
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.fiscal_years import service as svc
from app.modules.fiscal_years.models import AccountingPeriod, FiscalYear
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/fiscal-years")


class FiscalYearCreateIn(BaseModel):
    start_date: date
    end_date: date
    name: str = Field(default="", max_length=64)


class FiscalYearOut(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date
    is_open: bool


class PeriodOut(BaseModel):
    id: str
    start_date: date
    end_date: date
    is_open: bool


@router.get("", response_model=list[FiscalYearOut])
def list_fiscal_years(
    ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)
):
    rows = session.execute(
        select(FiscalYear)
        .where(FiscalYear.company_id == ctx.company_id)
        .order_by(FiscalYear.start_date.desc())
    ).scalars().all()
    return [FiscalYearOut(id=f.id, name=f.name, start_date=f.start_date, end_date=f.end_date, is_open=f.is_open) for f in rows]


@router.post("", response_model=FiscalYearOut, status_code=201)
def create_fiscal_year(
    payload: FiscalYearCreateIn,
    ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)),
    session: Session = Depends(get_db),
):
    fy = svc.create_fiscal_year(
        session,
        company_id=ctx.company_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        actor_user_id=ctx.user.id,
        name=payload.name,
    )
    log_action(session, action="fiscal_year.created", entity_type="fiscal_year", entity_id=fy.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return FiscalYearOut(id=fy.id, name=fy.name, start_date=fy.start_date, end_date=fy.end_date, is_open=fy.is_open)


@router.get("/{fy_id}/periods", response_model=list[PeriodOut])
def list_periods(fy_id: str, ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)):
    fy = session.get(FiscalYear, fy_id)
    if fy is None or fy.company_id != ctx.company_id:
        raise NotFoundError("Fiscal year")
    periods = session.execute(
        select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fy_id).order_by(AccountingPeriod.start_date)
    ).scalars().all()
    return [PeriodOut(id=p.id, start_date=p.start_date, end_date=p.end_date, is_open=p.is_open) for p in periods]


@router.post("/{fy_id}/periods/{period_id}/close", status_code=200)
def close_period(period_id: str, ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)):
    period = session.get(AccountingPeriod, period_id)
    if period is None or period.company_id != ctx.company_id:
        raise NotFoundError("Accounting period")
    period.is_open = False
    session.flush()
    log_action(session, action="period.closed", entity_type="accounting_period", entity_id=period.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return {"id": period.id, "is_open": period.is_open}


@router.post("/{fy_id}/close", status_code=200)
def close_fiscal_year(fy_id: str, ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)):
    fy = svc.close_fiscal_year(session, fy_id, ctx.user.id)
    log_action(session, action="fiscal_year.closed", entity_type="fiscal_year", entity_id=fy.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return {"id": fy.id, "is_open": fy.is_open}


@router.get("/resolve/{on_date}")
def resolve(on_date: date, ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)):
    fy = svc.resolve_fiscal_year(session, company_id=ctx.company_id, on_date=on_date)
    return {"fiscal_year": None if fy is None else {"id": fy.id, "name": fy.name, "is_open": fy.is_open}}
