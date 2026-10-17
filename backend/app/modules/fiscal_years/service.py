"""Fiscal year service: calendar, period guard, and the year-end lifecycle.

Lifecycle (all posted through the centralized accounting pipeline):
  * opening balances — first journal of a fresh fiscal year (new database)
  * close             — zeroes cumulative P&L into retained earnings, then
                        seals the year and every period in it
  * forward           — mirrors closing balance-sheet balances into the next
                        fiscal year as one balanced carry-forward entry
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

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


def close_fiscal_year(session: Session, fiscal_year_id: str, actor_user_id: str) -> tuple[FiscalYear, str | None]:
    """Close a fiscal year: post the cumulative P&L → retained-earnings
    closing entry, then seal the year and all of its periods.

    Returns (fiscal_year, closing_entry_id | None). The closing entry zeroes
    every income/expense account from inception through the year's end date
    (so years closed out of order or with legacy unclosed history still end at
    zero), and lands on the year's end date even if that month's period was
    already closed by hand.
    """
    fy = session.get(FiscalYear, fiscal_year_id)
    if fy is None:
        raise NotFoundError("Fiscal year")
    if not fy.is_open:
        raise ConflictError("FISCAL_YEAR_CLOSED", f"Fiscal year {fy.name} is already closed")

    # Years must be closed in chronological order in both directions:
    # closing a later year first would let its cumulative closing entry
    # double-count against an earlier year closed afterwards.
    earlier_open = session.scalar(
        select(FiscalYear.id).where(
            FiscalYear.company_id == fy.company_id,
            FiscalYear.end_date < fy.start_date,
            FiscalYear.is_open.is_(True),
        )
    )
    if earlier_open is not None:
        raise BusinessRuleError(
            "CLOSE_OUT_OF_ORDER",
            "An earlier fiscal year is still open; close years in chronological order",
        )
    later_closed = session.scalar(
        select(FiscalYear.id).where(
            FiscalYear.company_id == fy.company_id,
            FiscalYear.start_date > fy.end_date,
            FiscalYear.is_open.is_(False),
        )
    )
    if later_closed is not None:
        raise BusinessRuleError(
            "CLOSE_OUT_OF_ORDER",
            "A later fiscal year is already closed; close years in chronological order",
        )

    closing_entry_id = _post_year_end_closing(session, fy, actor_user_id)

    for period in session.execute(
        select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fy.id)
    ).scalars():
        period.is_open = False
    fy.is_open = False
    fy.closed_at = datetime.now(timezone.utc)
    fy.closed_by = actor_user_id
    session.flush()
    return fy, closing_entry_id


def _post_year_end_closing(
    session: Session, fy: FiscalYear, actor_user_id: str
) -> str | None:
    """Post the closing journal: debit income, credit expense, balance to
    retained earnings. Returns the entry id, or None when there is no P&L
    activity to close (fresh/never-used year)."""
    # Local import: accounting.service imports this module at package level.
    from app.modules.accounting.service import (
        JournalLineSpec,
        SourceRef,
        account_code_map,
        post_journal_entry,
        trial_balance,
    )
    from app.modules.companies.models import Company
    from app.shared.money import money

    # Cumulative to year end: zeroes legacy unclosed history in the same pass,
    # and ignores carry-forward snapshots (they duplicate prior-year detail).
    tb = trial_balance(
        session, fy.company_id, from_date=None, to_date=fy.end_date,
        exclude_carry_forward=True,
    )
    pnl = [
        row for row in tb
        if row["account_type"] in ("income", "expense") and row["balance"] != 0
    ]
    if not pnl:
        return None

    lines: list[JournalLineSpec] = []
    pnl_signed = Decimal("0")
    for row in pnl:
        balance = money(row["balance"])  # debit - credit
        pnl_signed += balance
        lines.append(
            JournalLineSpec(
                account_code=row["account_code"],
                side="debit" if balance < 0 else "credit",
                amount_base=abs(balance),
                description=f"Year-end closing {fy.name}",
            )
        )
    # Balance the entry: pnl_signed is debit-positive, so a net credit
    # balance (profit) is absorbed by a credit to retained earnings.
    if pnl_signed != 0:
        re_code = account_code_map(session, fy.company_id)["retained_earnings"]
        lines.append(
            JournalLineSpec(
                account_code=re_code,
                side="debit" if pnl_signed > 0 else "credit",
                amount_base=abs(pnl_signed),
                description=f"Profit/loss carried to retained earnings ({fy.name})",
            )
        )
    if len(lines) < 2:
        return None

    company = session.get(Company, fy.company_id)
    if company is None:
        raise NotFoundError("Company")
    entry = post_journal_entry(
        session,
        company_id=fy.company_id,
        entry_date=fy.end_date,
        source=SourceRef(type="year_end_close", id=fy.id),
        lines=lines,
        description=f"Year-end closing {fy.name or fy.start_date.year}",
        actor_user_id=actor_user_id,
        currency=company.base_currency,
        base_currency=company.base_currency,
        allow_closed_period=True,
    )
    return entry.id


def post_opening_balances(
    session: Session,
    *,
    fiscal_year_id: str,
    company_id: str,
    actor_user_id: str,
    lines: list[dict],
    entry_date: date | None = None,
    description: str | None = None,
):
    """Post opening balances as the fiscal year's first journal entry.

    Intended for a fresh/new database: the target year must be open and must
    not contain any posted activity yet, so opening balances can never be
    double-entered or appended after operations began.
    """
    from app.modules.accounting.service import JournalLineSpec, SourceRef, post_journal_entry
    from app.modules.companies.models import Company

    fy = session.get(FiscalYear, fiscal_year_id)
    if fy is None or fy.company_id != company_id:
        raise NotFoundError("Fiscal year")
    if not fy.is_open:
        raise BusinessRuleError("FISCAL_YEAR_CLOSED", f"Fiscal year {fy.name} is closed")

    from app.modules.accounting.models import JournalEntry

    existing = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= fy.start_date,
            JournalEntry.entry_date <= fy.end_date,
            JournalEntry.status == "posted",
        )
    )
    if existing is not None:
        raise ConflictError(
            "FY_HAS_ACTIVITY",
            "This fiscal year already has posted entries; opening balances must come first",
        )

    on_date = entry_date or fy.start_date
    if on_date < fy.start_date or on_date > fy.end_date:
        raise BusinessRuleError(
            "DATE_OUTSIDE_FISCAL_YEAR",
            f"Opening balance date must fall within {fy.start_date} .. {fy.end_date}",
        )

    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    specs = [
        JournalLineSpec(
            account_code=line["account_code"],
            side=line["side"],
            amount_base=line["amount"],
            description=line.get("description") or "Opening balance",
        )
        for line in lines
    ]
    return post_journal_entry(
        session,
        company_id=company_id,
        entry_date=on_date,
        source=SourceRef(type="opening", id=fy.id),
        lines=specs,
        description=description or f"Opening balances {fy.name}",
        actor_user_id=actor_user_id,
        currency=company.base_currency,
        base_currency=company.base_currency,
    )


def _next_fiscal_range(fy: FiscalYear) -> tuple[date, date]:
    start = fy.end_date + timedelta(days=1)
    try:
        end = date(start.year + 1, start.month, start.day) - timedelta(days=1)
    except ValueError:  # Feb 29 in a non-leap target year
        end = date(start.year + 1, 3, 1) - timedelta(days=1)
    return start, end


def forward_fiscal_year(
    session: Session, *, fiscal_year_id: str, company_id: str, actor_user_id: str
) -> dict:
    """Carry a closed year's closing balances into the next fiscal year.

    Creates the next fiscal year when it does not exist yet, then posts one
    balanced carry-forward entry on its start date: every balance-sheet
    account mirrored at its closing balance, with any unclosed P&L residual
    absorbed into retained earnings (legacy years closed before this lifecycle
    existed). The entry is a snapshot — cumulative reports exclude it so
    balances are never double-counted, while reports scoped to the new year
    show it as the opening position.
    """
    from app.modules.accounting.models import JournalEntry
    from app.modules.accounting.service import (
        JournalLineSpec,
        SourceRef,
        account_code_map,
        post_journal_entry,
        trial_balance,
    )
    from app.modules.companies.models import Company
    from app.shared.money import money

    fy = session.get(FiscalYear, fiscal_year_id)
    if fy is None or fy.company_id != company_id:
        raise NotFoundError("Fiscal year")
    if fy.is_open:
        raise BusinessRuleError(
            "FY_NOT_CLOSED", "Close the fiscal year before forwarding its balances"
        )
    already = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.company_id == company_id,
            JournalEntry.source_type == "carry_forward",
            JournalEntry.source_id == fy.id,
        )
    )
    if already is not None:
        raise ConflictError("ALREADY_FORWARDED", f"Fiscal year {fy.name} was already forwarded")

    # Target: the earliest later year, created on demand.
    target = session.scalar(
        select(FiscalYear).where(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date > fy.end_date,
        ).order_by(FiscalYear.start_date)
    )
    created = False
    if target is None:
        start, end = _next_fiscal_range(fy)
        target = create_fiscal_year(
            session, company_id=company_id, start_date=start, end_date=end,
            actor_user_id=actor_user_id,
        )
        created = True
    elif not target.is_open:
        raise ConflictError(
            "TARGET_FY_CLOSED",
            f"The next fiscal year {target.name} is closed; reopen it before forwarding",
        )

    # Refuse to overwrite an already-active target year (other than the
    # carry-forward we are about to post).
    target_has_activity = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= target.start_date,
            JournalEntry.entry_date <= target.end_date,
            JournalEntry.status == "posted",
        )
    )
    if target_has_activity is not None:
        raise ConflictError(
            "TARGET_FY_HAS_ACTIVITY",
            f"Fiscal year {target.name} already has posted entries; cannot forward into it",
        )

    tb = trial_balance(
        session, company_id, from_date=None, to_date=fy.end_date,
        exclude_carry_forward=True,
    )
    re_code = account_code_map(session, company_id)["retained_earnings"]

    lines: list[JournalLineSpec] = []
    mirrored = Decimal("0")  # signed sum of mirrored balance-sheet rows
    for row in tb:
        if row["account_type"] not in ("asset", "liability", "equity"):
            continue
        balance = money(row["balance"])
        if balance == 0 or row["account_code"] == re_code:
            continue  # retained earnings is recomputed below as the plug
        mirrored += balance
        lines.append(
            JournalLineSpec(
                account_code=row["account_code"],
                side="debit" if balance > 0 else "credit",
                amount_base=abs(balance),
                description=f"Carried forward from {fy.name}",
            )
        )

    # Retained earnings = its own closing balance + any unclosed P&L residual,
    # expressed as the balancing side of everything mirrored above.
    pnl_residual = Decimal("0")
    for row in tb:
        if row["account_type"] in ("income", "expense"):
            pnl_residual += money(row["balance"])
    re_signed = -(mirrored)  # plug so the entry balances; because the trial
    # balance sums to zero this equals RE's own balance plus any P&L residual.
    if re_signed != 0:
        lines.append(
            JournalLineSpec(
                account_code=re_code,
                side="debit" if re_signed > 0 else "credit",
                amount_base=abs(re_signed),
                description=f"Opening retained earnings from {fy.name}",
            )
        )

    if len(lines) < 2:
        raise BusinessRuleError(
            "NOTHING_TO_FORWARD", f"Fiscal year {fy.name} has no balances to forward"
        )

    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    entry = post_journal_entry(
        session,
        company_id=company_id,
        entry_date=target.start_date,
        source=SourceRef(type="carry_forward", id=fy.id),
        lines=lines,
        description=f"Opening balances carried forward from {fy.name}",
        actor_user_id=actor_user_id,
        currency=company.base_currency,
        base_currency=company.base_currency,
    )
    return {
        "from_fiscal_year_id": fy.id,
        "to_fiscal_year_id": target.id,
        "to_created": created,
        "journal_entry_id": entry.id,
        "doc_number": entry.doc_number,
        "accounts_carried": len(lines),
    }


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
