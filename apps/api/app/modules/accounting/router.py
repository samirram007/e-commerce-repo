"""Accounting HTTP routes: chart of accounts, journals, statement reports."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_ACCOUNTS_MANAGE, P_JOURNAL_POST, P_JOURNAL_VIEW, P_REPORTS_VIEW
from app.db.unit_of_work import get_db
from app.modules.accounting import service as svc
from app.modules.accounting.models import Account, JournalEntry, JournalLine
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter()


# ---- schema I/O ----
class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    account_type: str
    normal_side: str
    is_cash_or_bank: bool
    is_system: bool


class AccountCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    account_type: str
    normal_side: str = "debit"


class JournalLineIn(BaseModel):
    account_code: str
    side: str
    amount: Decimal = Field(gt=0)
    party_ref: str | None = None
    description: str | None = None


class ManualJournalIn(BaseModel):
    entry_date: date
    description: str | None = None
    currency: str | None = None
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    lines: list[JournalLineIn] = Field(min_length=2)


class JournalOut(BaseModel):
    id: str
    fiscal_year_id: str | None
    doc_number: str
    entry_date: date
    description: str | None
    status: str
    source_type: str
    source_id: str
    reversal_of_id: str | None
    created_by: str | None
    lines: list["JournalLineOutQ"]


class JournalLineOutQ(BaseModel):
    id: str
    account_code: str
    account_name: str
    side: str
    amount: Decimal
    description: str | None
    party_ref: str | None


class TrialBalanceRow(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


def _entry_out(session: Session, entry: JournalEntry) -> JournalOut:
    lines = session.execute(
        select(JournalLine).where(JournalLine.entry_id == entry.id).order_by(JournalLine.line_number)
    ).scalars().all()
    out_lines = []
    for line in lines:
        account = session.get(Account, line.account_id)
        out_lines.append(
            JournalLineOutQ(
                id=line.id,
                account_code=account.code if account else "",
                account_name=account.name if account else "",
                side=line.side,
                amount=line.amount,
                description=line.description,
                party_ref=line.party_ref,
            )
        )
    return JournalOut(
        id=entry.id,
        fiscal_year_id=entry.fiscal_year_id,
        doc_number=entry.doc_number,
        entry_date=entry.entry_date,
        description=entry.description,
        status=entry.status,
        source_type=entry.source_type,
        source_id=entry.source_id,
        reversal_of_id=entry.reversal_of_id,
        created_by=entry.created_by,
        lines=out_lines,
    )


# ---- accounts ----
@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    ctx: CompanyCtx = Depends(guard(P_JOURNAL_VIEW)), session: Session = Depends(get_db)
):
    rows = session.execute(
        select(Account).where(Account.company_id == ctx.company_id).order_by(Account.code)
    ).scalars().all()
    return [AccountOut.model_validate(a) for a in rows]


@router.post("/accounts/seed-defaults", response_model=list[AccountOut], status_code=201)
def seed_default_accounts(
    ctx: CompanyCtx = Depends(guard(P_ACCOUNTS_MANAGE)), session: Session = Depends(get_db)
):
    """Idempotently create any missing default chart accounts (first-run/new
    database setup). Accounts already present are left untouched."""
    from app.modules.companies.service import get_company

    company = get_company(session, ctx.company_id)
    svc.create_default_chart(session, company=company)
    rows = session.execute(
        select(Account).where(Account.company_id == ctx.company_id).order_by(Account.code)
    ).scalars().all()
    log_action(
        session, action="account.chart_seeded", entity_type="company",
        entity_id=company.id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return [AccountOut.model_validate(a) for a in rows]


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreateIn,
    ctx: CompanyCtx = Depends(guard(P_ACCOUNTS_MANAGE)),
    session: Session = Depends(get_db),
):
    account = svc.create_account(
        session,
        company_id=ctx.company_id,
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        normal_side=payload.normal_side,
    )
    log_action(session, action="account.created", entity_type="account", entity_id=account.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return AccountOut.model_validate(account)


# ---- journals ----
@router.get("/journal-entries", response_model=list[JournalOut])
def list_journals(
    fiscal_year_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_JOURNAL_VIEW)),
    session: Session = Depends(get_db),
):
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.company_id == ctx.company_id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.doc_number.desc())
        .limit(500)
    )
    if fiscal_year_id:
        stmt = stmt.where(JournalEntry.fiscal_year_id == fiscal_year_id)
    rows = session.execute(stmt).scalars().all()
    return [_entry_out(session, e) for e in rows]


@router.get("/journal-entries/{entry_id}", response_model=JournalOut)
def get_journal(
    entry_id: str, ctx: CompanyCtx = Depends(guard(P_JOURNAL_VIEW)), session: Session = Depends(get_db)
):
    entry = session.get(JournalEntry, entry_id)
    if entry is None or entry.company_id != ctx.company_id:
        raise NotFoundError("Journal entry")
    return _entry_out(session, entry)


@router.post("/journal-entries", response_model=JournalOut, status_code=201)
def post_manual_journal(
    payload: ManualJournalIn,
    ctx: CompanyCtx = Depends(guard(P_JOURNAL_POST)),
    session: Session = Depends(get_db),
):
    from app.modules.companies.service import get_company

    company = get_company(session, ctx.company_id)
    specs = [
        svc.JournalLineSpec(
            account_code=l.account_code,
            side=l.side,
            amount_base=l.amount,
            party_ref=l.party_ref,
            description=l.description,
        )
        for l in payload.lines
    ]
    entry = svc.post_journal_entry(
        session,
        company_id=ctx.company_id,
        entry_date=payload.entry_date,
        source=svc.SourceRef(type="manual", id=ctx.company_id),
        lines=specs,
        description=payload.description,
        actor_user_id=ctx.user.id,
        currency=payload.currency or company.base_currency,
        exchange_rate=payload.exchange_rate,
        base_currency=company.base_currency,
    )
    log_action(session, action="journal.posted", entity_type="journal_entry", entity_id=entry.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _entry_out(session, entry)


@router.post("/journal-entries/{entry_id}/reverse", response_model=JournalOut, status_code=201)
def reverse_journal(
    entry_id: str,
    ctx: CompanyCtx = Depends(guard(P_JOURNAL_POST)),
    session: Session = Depends(get_db),
):
    entry = session.get(JournalEntry, entry_id)
    if entry is None or entry.company_id != ctx.company_id:
        raise NotFoundError("Journal entry")
    reversal = svc.reverse_entry(session, entry, actor_user_id=ctx.user.id)
    log_action(session, action="journal.reversed", entity_type="journal_entry", entity_id=reversal.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"reversal_of": entry.id})
    return _entry_out(session, reversal)


# ---- statements ----
@router.get("/reports/trial-balance", response_model=list[TrialBalanceRow])
def trial_balance(
    from_date: date | None = None,
    to_date: date | None = None,
    fiscal_year_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.trial_balance(
        session, ctx.company_id, from_date=from_date, to_date=to_date, fiscal_year_id=fiscal_year_id
    )
    return [TrialBalanceRow(**r) for r in rows]


@router.get("/reports/profit-and-loss")
def profit_and_loss(
    from_date: date,
    to_date: date,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    p = svc.profit_and_loss(session, ctx.company_id, from_date=from_date, to_date=to_date)
    return {"from_date": str(p["from_date"]), "to_date": str(p["to_date"]), "income": str(p["income"]), "expense": str(p["expense"]), "profit": str(p["profit"])}


@router.get("/reports/balance-sheet")
def balance_sheet(
    as_of: date,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    b = svc.balance_sheet(session, ctx.company_id, as_of=as_of)
    return {"as_of": str(b["as_of"]), "assets": str(b["assets"]), "liabilities": str(b["liabilities"]), "equity_total": str(b["equity_total"]), "balanced": b["check_liabilities_plus_equity"] == 0}


@router.get("/reports/general-ledger")
def general_ledger(
    account_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    fiscal_year_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_REPORTS_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.general_ledger(
        session,
        ctx.company_id,
        account_code=account_code,
        from_date=from_date,
        to_date=to_date,
        fiscal_year_id=fiscal_year_id,
    )
    return [
        {
            "doc_number": r["doc_number"],
            "entry_date": str(r["entry_date"]),
            "source_type": r["source_type"],
            "account_code": r["account_code"],
            "account_name": r["account_name"],
            "side": r["side"],
            "amount": str(r["amount"]),
            "description": r["description"],
        }
        for r in rows
    ]
