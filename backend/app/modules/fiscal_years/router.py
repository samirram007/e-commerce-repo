"""Fiscal year HTTP routes: calendar, periods, and the year-end lifecycle
(opening balances → close → forward)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_FISCAL_MANAGE, P_JOURNAL_POST
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
    fy = session.get(FiscalYear, fy_id)
    if fy is None or fy.company_id != ctx.company_id:
        raise NotFoundError("Fiscal year")
    fy, closing_entry_id = svc.close_fiscal_year(session, fy_id, ctx.user.id)
    log_action(
        session, action="fiscal_year.closed", entity_type="fiscal_year", entity_id=fy.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"closing_entry_id": closing_entry_id},
    )
    return {
        "id": fy.id,
        "is_open": fy.is_open,
        "closing_entry_id": closing_entry_id,
        "periods_closed": True,
    }


# ------------------------------------------------- year-end lifecycle

class OpeningLineIn(BaseModel):
    account_code: str = Field(min_length=1, max_length=20)
    side: str  # debit | credit — validated by the posting pipeline
    amount: Decimal = Field(gt=0)
    description: str | None = Field(default=None, max_length=200)


class OpeningBalancesIn(BaseModel):
    entry_date: date | None = None  # defaults to the fiscal year's start
    description: str | None = Field(default=None, max_length=200)
    lines: list[OpeningLineIn] = Field(min_length=2)


class OpeningBalancesOut(BaseModel):
    id: str
    doc_number: str
    entry_date: date
    fiscal_year_id: str | None
    status: str


class ForwardOut(BaseModel):
    from_fiscal_year_id: str
    to_fiscal_year_id: str
    to_created: bool
    journal_entry_id: str
    doc_number: str
    accounts_carried: int


@router.post("/{fy_id}/opening-balances", response_model=OpeningBalancesOut, status_code=201)
def post_opening_balances(
    fy_id: str,
    payload: OpeningBalancesIn,
    ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE, P_JOURNAL_POST)),
    session: Session = Depends(get_db),
):
    """Post opening balances as the year's first journal (fresh/new database)."""
    entry = svc.post_opening_balances(
        session,
        fiscal_year_id=fy_id,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        lines=[line.model_dump() for line in payload.lines],
        entry_date=payload.entry_date,
        description=payload.description,
    )
    log_action(
        session, action="fiscal_year.opening_posted", entity_type="journal_entry",
        entity_id=entry.id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"fiscal_year_id": fy_id},
    )
    return OpeningBalancesOut(
        id=entry.id,
        doc_number=entry.doc_number,
        entry_date=entry.entry_date,
        fiscal_year_id=entry.fiscal_year_id,
        status=entry.status,
    )


@router.post("/{fy_id}/forward", response_model=ForwardOut, status_code=201)
def forward_fiscal_year(
    fy_id: str,
    ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE, P_JOURNAL_POST)),
    session: Session = Depends(get_db),
):
    """Carry a closed year's balances into the next fiscal year (creating it
    when needed) as one balanced carry-forward entry."""
    result = svc.forward_fiscal_year(
        session, fiscal_year_id=fy_id, company_id=ctx.company_id, actor_user_id=ctx.user.id
    )
    log_action(
        session, action="fiscal_year.forwarded", entity_type="fiscal_year",
        entity_id=fy_id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"to_fiscal_year_id": result["to_fiscal_year_id"]},
    )
    return ForwardOut(**result)


@router.get("/resolve/{on_date}")
def resolve(on_date: date, ctx: CompanyCtx = Depends(guard(P_FISCAL_MANAGE)), session: Session = Depends(get_db)):
    fy = svc.resolve_fiscal_year(session, company_id=ctx.company_id, on_date=on_date)
    return {"fiscal_year": None if fy is None else {"id": fy.id, "name": fy.name, "is_open": fy.is_open}}
