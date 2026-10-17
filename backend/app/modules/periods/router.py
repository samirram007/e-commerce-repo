"""Period context HTTP routes.

Available to any authenticated member of a company (a user period context is a
personal preference, not an administrative setting) — unlike `/fiscal-years`,
which is gated by `fiscal.manage`.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, current_company_ctx
from app.modules.periods import service as svc
from app.modules.periods.schemas import (
    AccountingPeriodOption,
    FiscalYearOption,
    PeriodContextIn,
    PeriodContextOut,
    ReportingPeriodIn,
    ReportingPeriodOut,
    ReportingPeriodUpdateIn,
)

router = APIRouter()


def _ctx(ctx: CompanyCtx = Depends(current_company_ctx)) -> CompanyCtx:
    """Period context requires a concrete company scope."""
    if ctx.company_id is None:
        raise ForbiddenError("Company context required")
    return ctx


def _fy_out(fy) -> FiscalYearOption:
    return FiscalYearOption(
        id=fy.id, name=fy.name, start_date=fy.start_date, end_date=fy.end_date, is_open=fy.is_open
    )


def _ap_out(ap) -> AccountingPeriodOption:
    return AccountingPeriodOption(
        id=ap.id, fiscal_year_id=ap.fiscal_year_id, start_date=ap.start_date,
        end_date=ap.end_date, is_open=ap.is_open,
    )


def _rp_out(rp) -> ReportingPeriodOut:
    return ReportingPeriodOut(
        id=rp.id, name=rp.name, start_date=rp.start_date, end_date=rp.end_date
    )


def _context_out(resolved) -> PeriodContextOut:
    return PeriodContextOut(
        fiscal_year=_fy_out(resolved.fiscal_year) if resolved.fiscal_year else None,
        accounting_period=_ap_out(resolved.accounting_period) if resolved.accounting_period else None,
        reporting_period=_rp_out(resolved.reporting_period) if resolved.reporting_period else None,
        effective_from=resolved.effective_from,
        effective_to=resolved.effective_to,
    )


# --------------------------------------------------------------------- context

@router.get("/period-context", response_model=PeriodContextOut)
def get_period_context(ctx: CompanyCtx = Depends(_ctx), session: Session = Depends(get_db)):
    resolved = svc.resolve_context(session, user_id=ctx.user.id, company_id=ctx.company_id)
    return _context_out(resolved)


@router.put("/period-context", response_model=PeriodContextOut)
def set_period_context(
    payload: PeriodContextIn,
    ctx: CompanyCtx = Depends(_ctx),
    session: Session = Depends(get_db),
):
    svc.set_preference(
        session,
        user_id=ctx.user.id,
        company_id=ctx.company_id,
        fiscal_year_id=payload.fiscal_year_id,
        accounting_period_id=payload.accounting_period_id,
        reporting_period_id=payload.reporting_period_id,
    )
    log_action(
        session,
        action="period_context.updated",
        entity_type="user_period_preference",
        entity_id=ctx.user.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
    )
    resolved = svc.resolve_context(session, user_id=ctx.user.id, company_id=ctx.company_id)
    return _context_out(resolved)


@router.get("/period-context/fiscal-years", response_model=list[FiscalYearOption])
def list_fiscal_year_options(ctx: CompanyCtx = Depends(_ctx), session: Session = Depends(get_db)):
    return [_fy_out(fy) for fy in svc.list_fiscal_year_options(session, company_id=ctx.company_id)]


@router.get(
    "/period-context/fiscal-years/{fy_id}/periods", response_model=list[AccountingPeriodOption]
)
def list_accounting_period_options(
    fy_id: str, ctx: CompanyCtx = Depends(_ctx), session: Session = Depends(get_db)
):
    rows = svc.list_accounting_period_options(session, company_id=ctx.company_id, fiscal_year_id=fy_id)
    return [_ap_out(ap) for ap in rows]


# --------------------------------------------------------------------- reporting periods

@router.get("/reporting-periods", response_model=list[ReportingPeriodOut])
def list_reporting_periods(ctx: CompanyCtx = Depends(_ctx), session: Session = Depends(get_db)):
    rows = svc.list_reporting_periods(session, company_id=ctx.company_id, user_id=ctx.user.id)
    return [_rp_out(rp) for rp in rows]


@router.post("/reporting-periods", response_model=ReportingPeriodOut, status_code=201)
def create_reporting_period(
    payload: ReportingPeriodIn,
    ctx: CompanyCtx = Depends(_ctx),
    session: Session = Depends(get_db),
):
    rp = svc.create_reporting_period(
        session,
        company_id=ctx.company_id,
        user_id=ctx.user.id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_action(
        session, action="reporting_period.created", entity_type="reporting_period",
        entity_id=rp.id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return _rp_out(rp)


@router.patch("/reporting-periods/{rp_id}", response_model=ReportingPeriodOut)
def update_reporting_period(
    rp_id: str,
    payload: ReportingPeriodUpdateIn,
    ctx: CompanyCtx = Depends(_ctx),
    session: Session = Depends(get_db),
):
    rp = svc.update_reporting_period(
        session,
        rp_id=rp_id,
        company_id=ctx.company_id,
        user_id=ctx.user.id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_action(
        session, action="reporting_period.updated", entity_type="reporting_period",
        entity_id=rp.id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return _rp_out(rp)


@router.delete("/reporting-periods/{rp_id}", status_code=204)
def delete_reporting_period(
    rp_id: str, ctx: CompanyCtx = Depends(_ctx), session: Session = Depends(get_db)
):
    svc.delete_reporting_period(
        session, rp_id=rp_id, company_id=ctx.company_id, user_id=ctx.user.id
    )
    log_action(
        session, action="reporting_period.deleted", entity_type="reporting_period",
        entity_id=rp_id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return Response(status_code=204)
