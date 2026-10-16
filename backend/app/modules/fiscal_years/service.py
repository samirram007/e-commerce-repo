"""Fiscal year service."""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import new_id
from app.modules.fiscal_years.models import AccountingPeriod, FiscalYear


def month_add(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # clamp to last day-of-month behavior not needed for period starts (1st)
    return date(year, month, 1)


def create_fiscal_year(
    session: Session, *, company_id: str, start_date: date, end_date: date, actor_user_id: str, name: str = ""
) -> FiscalYear:
    if start_date >= end_date:
        raise BusinessRuleError("INVALID_FISCAL_RANGE", "start_date must be before end_date")
    overlapping = session.scalar(
        select(FiscalYear.id).where(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date <= end_date,
            FiscalYear.end_date >= start_date,
        )
    )
    if overlapping is not None:
        raise BusinessRuleError(
            "FISCAL_YEAR_EXISTS", "A fiscal year overlapping this range already exists"
        )
    fy = FiscalYear(
        company_id=company_id,
        name=name or f"FY{start_date.year}",
        start_date=start_date,
        end_date=end_date,
        created_by=actor_user_id,
    )
    session.add(fy)
    session.flush()
    # Monthly periods, clamped to the fiscal-year boundaries
    cur = start_date
    from datetime import timedelta

    while cur <= end_date:
        period_start = max(cur, start_date)
        next_month = month_add(cur, 1)
        if next_month > end_date:
            period_end = end_date
        else:
            period_end = date(next_month.year, next_month.month, 1) - timedelta(days=1)
        session.add(
            AccountingPeriod(
                fiscal_year_id=fy.id,
                company_id=company_id,
                start_date=period_start,
                end_date=period_end,
            )
        )
        cur = next_month
    session.flush()
    return fy


def close_fiscal_year(session: Session, fiscal_year_id: str, actor_user_id: str) -> FiscalYear:
    from app.modules.inventory.service import has_open_variances

    fy = session.get(FiscalYear, fiscal_year_id)
    if fy is None:
        raise NotFoundError("Fiscal year")
    closed_periods = (
        session.execute(
            select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fy.id)
        ).scalars().all()
    )
    if any(p.is_open for p in closed_periods):
        for p in closed_periods:
            p.is_open = False
    fy.is_open = False
    fy.closed_at = datetime.now(timezone.utc)
    fy.closed_by = actor_user_id
    session.flush()
    return fy


def resolve_fiscal_year(session: Session, *, company_id: str, on_date: date) -> FiscalYear | None:
    return session.scalar(
        select(FiscalYear).where(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date <= on_date,
            FiscalYear.end_date >= on_date,
        )
    )


def get_open_fiscal_year(session: Session, *, company_id: str, on_date: date) -> FiscalYear:
    fy = resolve_fiscal_year(session, company_id=company_id, on_date=on_date)
    if fy is None:
        raise BusinessRuleError(
            "NO_FISCAL_YEAR",
            f"No fiscal year defined for {on_date}; create the fiscal year before posting",
        )
    return fy


def ensure_period_open(session: Session, *, company_id: str, on_date: date) -> FiscalYear:
    """Validate that `on_date` falls in an open period of an open fiscal year."""
    fy = get_open_fiscal_year(session, company_id=company_id, on_date=on_date)
    if not fy.is_open:
        raise BusinessRuleError("FISCAL_YEAR_CLOSED", f"Fiscal year {fy.name} is closed")
    period = session.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.fiscal_year_id == fy.id,
            AccountingPeriod.start_date <= on_date,
            AccountingPeriod.end_date >= on_date,
        )
    )
    if period is None:
        raise BusinessRuleError("NO_ACCOUNTING_PERIOD", f"No accounting period covers {on_date}")
    if not period.is_open:
        raise BusinessRuleError("PERIOD_CLOSED", f"Accounting period around {on_date} is closed")
    return fy
