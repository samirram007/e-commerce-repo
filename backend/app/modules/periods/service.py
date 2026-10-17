"""Period context service: user period preferences + reporting-period CRUD.

Services never commit; the request-scoped UoW owns the transaction.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.fiscal_years.models import AccountingPeriod, FiscalYear
from app.modules.periods.models import ReportingPeriod, UserPeriodPreference


# --------------------------------------------------------------------- reporting periods

def list_reporting_periods(session: Session, *, company_id: str, user_id: str) -> list[ReportingPeriod]:
    return list(
        session.execute(
            select(ReportingPeriod)
            .where(ReportingPeriod.company_id == company_id, ReportingPeriod.user_id == user_id)
            .order_by(ReportingPeriod.start_date.desc(), ReportingPeriod.name)
        ).scalars()
    )


def get_reporting_period(session: Session, *, rp_id: str, company_id: str, user_id: str) -> ReportingPeriod:
    rp = session.get(ReportingPeriod, rp_id)
    if rp is None or rp.company_id != company_id or rp.user_id != user_id:
        raise NotFoundError("Reporting period")
    return rp


def _validate_range(start_date: date, end_date: date) -> None:
    if start_date >= end_date:
        raise BusinessRuleError("INVALID_REPORTING_RANGE", "start_date must be before end_date")


def _name_taken(session: Session, *, company_id: str, user_id: str, name: str, exclude_id: str | None = None) -> bool:
    stmt = select(ReportingPeriod.id).where(
        ReportingPeriod.company_id == company_id,
        ReportingPeriod.user_id == user_id,
        ReportingPeriod.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(ReportingPeriod.id != exclude_id)
    return session.scalar(stmt) is not None


def create_reporting_period(
    session: Session,
    *,
    company_id: str,
    user_id: str,
    name: str,
    start_date: date,
    end_date: date,
) -> ReportingPeriod:
    _validate_range(start_date, end_date)
    if _name_taken(session, company_id=company_id, user_id=user_id, name=name):
        raise ConflictError("REPORTING_PERIOD_EXISTS", "A reporting period with this name already exists")
    rp = ReportingPeriod(
        company_id=company_id,
        user_id=user_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        created_by=user_id,
    )
    session.add(rp)
    session.flush()
    return rp


def update_reporting_period(
    session: Session,
    *,
    rp_id: str,
    company_id: str,
    user_id: str,
    name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportingPeriod:
    rp = get_reporting_period(session, rp_id=rp_id, company_id=company_id, user_id=user_id)
    new_name = rp.name if name is None else name
    new_start = rp.start_date if start_date is None else start_date
    new_end = rp.end_date if end_date is None else end_date
    _validate_range(new_start, new_end)
    if new_name != rp.name and _name_taken(
        session, company_id=company_id, user_id=user_id, name=new_name, exclude_id=rp.id
    ):
        raise ConflictError("REPORTING_PERIOD_EXISTS", "A reporting period with this name already exists")
    rp.name = new_name
    rp.start_date = new_start
    rp.end_date = new_end
    session.flush()
    return rp


def delete_reporting_period(session: Session, *, rp_id: str, company_id: str, user_id: str) -> None:
    rp = get_reporting_period(session, rp_id=rp_id, company_id=company_id, user_id=user_id)
    # Detach from any preference so the resolution never points at a deleted row.
    for pref in session.execute(
        select(UserPeriodPreference).where(UserPeriodPreference.reporting_period_id == rp.id)
    ).scalars():
        pref.reporting_period_id = None
    session.delete(rp)
    session.flush()


# --------------------------------------------------------------------- option lists

def list_fiscal_year_options(session: Session, *, company_id: str) -> list[FiscalYear]:
    return list(
        session.execute(
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .order_by(FiscalYear.start_date.desc())
        ).scalars()
    )


def list_accounting_period_options(session: Session, *, company_id: str, fiscal_year_id: str) -> list[AccountingPeriod]:
    fy = session.get(FiscalYear, fiscal_year_id)
    if fy is None or fy.company_id != company_id:
        raise NotFoundError("Fiscal year")
    return list(
        session.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.fiscal_year_id == fiscal_year_id)
            .order_by(AccountingPeriod.start_date)
        ).scalars()
    )


# --------------------------------------------------------------------- preference / context

def get_preference(session: Session, *, user_id: str, company_id: str) -> UserPeriodPreference | None:
    return session.scalar(
        select(UserPeriodPreference).where(
            UserPeriodPreference.user_id == user_id,
            UserPeriodPreference.company_id == company_id,
        )
    )


def set_preference(
    session: Session,
    *,
    user_id: str,
    company_id: str,
    fiscal_year_id: str | None,
    accounting_period_id: str | None,
    reporting_period_id: str | None,
) -> UserPeriodPreference:
    if fiscal_year_id is not None:
        fy = session.get(FiscalYear, fiscal_year_id)
        if fy is None or fy.company_id != company_id:
            raise NotFoundError("Fiscal year")

    if accounting_period_id is not None:
        ap = session.get(AccountingPeriod, accounting_period_id)
        if ap is None or ap.company_id != company_id:
            raise NotFoundError("Accounting period")
        if fiscal_year_id is not None and ap.fiscal_year_id != fiscal_year_id:
            raise BusinessRuleError(
                "PERIOD_FY_MISMATCH", "Accounting period does not belong to the selected fiscal year"
            )
        # Auto-fill the fiscal year from the period when omitted.
        if fiscal_year_id is None:
            fiscal_year_id = ap.fiscal_year_id

    if reporting_period_id is not None:
        get_reporting_period(session, rp_id=reporting_period_id, company_id=company_id, user_id=user_id)

    pref = get_preference(session, user_id=user_id, company_id=company_id)
    if pref is None:
        pref = UserPeriodPreference(user_id=user_id, company_id=company_id)
        session.add(pref)
    pref.fiscal_year_id = fiscal_year_id
    pref.accounting_period_id = accounting_period_id
    pref.reporting_period_id = reporting_period_id
    session.flush()
    return pref


class ResolvedContext:
    """Plain container for the resolved context (avoids importing schemas here)."""

    def __init__(
        self,
        *,
        fiscal_year: FiscalYear | None,
        accounting_period: AccountingPeriod | None,
        reporting_period: ReportingPeriod | None,
        effective_from: date | None,
        effective_to: date | None,
    ) -> None:
        self.fiscal_year = fiscal_year
        self.accounting_period = accounting_period
        self.reporting_period = reporting_period
        self.effective_from = effective_from
        self.effective_to = effective_to


def resolve_context(session: Session, *, user_id: str, company_id: str) -> ResolvedContext:
    pref = get_preference(session, user_id=user_id, company_id=company_id)
    if pref is None:
        return ResolvedContext(
            fiscal_year=None, accounting_period=None, reporting_period=None,
            effective_from=None, effective_to=None,
        )

    fy = session.get(FiscalYear, pref.fiscal_year_id) if pref.fiscal_year_id else None
    ap = session.get(AccountingPeriod, pref.accounting_period_id) if pref.accounting_period_id else None
    rp = session.get(ReportingPeriod, pref.reporting_period_id) if pref.reporting_period_id else None

    # Defensive: ignore rows that no longer belong to this company/user.
    if fy is not None and fy.company_id != company_id:
        fy = None
    if ap is not None and ap.company_id != company_id:
        ap = None
    if rp is not None and (rp.company_id != company_id or rp.user_id != user_id):
        rp = None

    # Precedence: explicit reporting period → accounting period → fiscal year.
    if rp is not None:
        effective_from, effective_to = rp.start_date, rp.end_date
    elif ap is not None:
        effective_from, effective_to = ap.start_date, ap.end_date
    elif fy is not None:
        effective_from, effective_to = fy.start_date, fy.end_date
    else:
        effective_from = effective_to = None

    return ResolvedContext(
        fiscal_year=fy,
        accounting_period=ap,
        reporting_period=rp,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def clamp_date_into_context(context: ResolvedContext, on_date: date | None = None) -> date | None:
    """Return `on_date` (default today) clamped into the active window.

    Used by document-creation forms to default a posting date that lands inside
    an open period of the selected context.
    """
    target = on_date or date.today()
    if context.effective_from is None or context.effective_to is None:
        return on_date
    if target < context.effective_from:
        return context.effective_from
    if target > context.effective_to:
        return context.effective_to
    return target
