"""Accounting service: single, centralized posting pipeline.

All modules post through `post_journal_entry` — never ad-hoc from routes.
Invariants enforced here:
  * every entry balances in the company base currency
  * entry date falls inside an open fiscal year + open period
  * posted entries are never mutated; corrections use reversal entries
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import new_id
from app.modules.accounting.models import Account, JournalEntry, JournalLine
from app.modules.companies.service import rate_for
from app.modules.fiscal_years.service import ensure_period_open, resolve_fiscal_year
from app.shared.money import dec, money
from app.shared.numbering import allocate_number

ACCOUNT_TYPE_ORDER = ["asset", "liability", "equity", "income", "expense"]

DEFAULT_CHART: list[tuple[str, str, str, str]] = [
    # code, name, type, normal_side
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1010", "Bank Account", "asset", "debit"),
    ("1100", "Accounts Receivable", "asset", "debit"),
    ("1150", "Sales Tax Payable (AR side)", "asset", "debit"),
    ("1200", "Inventory", "asset", "debit"),
    ("1250", "Stock in Transit", "asset", "debit"),
    ("1300", "Prepaid Expenses", "asset", "debit"),
    ("2000", "Accounts Payable", "liability", "credit"),
    ("2100", "Sales Tax Payable", "liability", "credit"),
    ("2200", "Accrued Liabilities", "liability", "credit"),
    ("2300", "Customer Credits", "liability", "credit"),
    ("3000", "Owner's Equity", "equity", "credit"),
    ("3100", "Retained Earnings", "equity", "credit"),
    ("4000", "Sales Revenue", "income", "credit"),
    ("4100", "Other Income", "income", "credit"),
    ("5000", "Cost of Goods Sold", "expense", "debit"),
    ("5100", "Purchases", "expense", "debit"),
    ("5200", "Inventory Variance", "expense", "debit"),
    ("5210", "Stock Shrinkage", "expense", "debit"),
    ("5300", "Freight-In Expense", "expense", "debit"),
    ("5400", "Freight-Out / Delivery Expense", "expense", "debit"),
    ("5500", "Discounts Given", "expense", "debit"),
    ("5600", "Returns Expense", "expense", "debit"),
    ("5700", "Refund Expense", "expense", "debit"),
    ("6000", "Operating Expenses", "expense", "debit"),
    ("6100", "Salaries & Wages Expense", "expense", "debit"),
    ("2400", "Payroll Payable", "liability", "credit"),
    ("2410", "Employee Withholdings Payable", "liability", "credit"),
]

# posting-source account role map used by other modules via get_account_codes
DEFAULT_ROLE_CODES = {
    "cash": "1000",
    "bank": "1010",
    "ar": "1100",
    "inventory": "1200",
    "stock_in_transit": "1250",
    "ap": "2000",
    "sales_tax_payable": "2100",
    "owner_equity": "3000",
    "retained_earnings": "3100",
    "sales_revenue": "4000",
    "cogs": "5000",
    "purchases": "5100",
    "inventory_variance": "5200",
    "stock_shrinkage": "5210",
    "freight_in": "5300",
    "freight_out": "5400",
    "discounts_given": "5500",
    "returns_expense": "5600",
    "refund_expense": "5700",
    "operating_expenses": "6000",
    "salaries_expense": "6100",
    "payroll_payable": "2400",
    "withholdings_payable": "2410",
}


def create_default_chart(session: Session, *, company: "object") -> None:
    for code, name, atype, side in DEFAULT_CHART:
        if session.scalar(select(Account.id).where(Account.company_id == company.id, Account.code == code)) is None:
            session.add(
                Account(
                    company_id=company.id,
                    code=code,
                    name=name,
                    account_type=atype,
                    normal_side=side,
                    is_system=True,
                    is_cash_or_bank=code in {"1000", "1010"},
                )
            )
    session.flush()


@dataclass(frozen=True)
class JournalLineSpec:
    account_code: str
    side: str  # debit | credit
    amount_base: Decimal
    party_ref: str | None = None
    description: str | None = None
    doc_currency_amount: Decimal | None = None


@dataclass(frozen=True)
class SourceRef:
    type: str
    id: str


def get_account_by_code(session: Session, company_id: str, code: str) -> Account:
    account = session.scalar(
        select(Account).where(Account.company_id == company_id, Account.code == code)
    )
    if account is None:
        raise NotFoundError(f"Account code {code}")
    return account


def account_code_map(session: Session, company_id: str) -> dict[str, str]:
    """role -> code for this company (uses DEFAULT_ROLE_CODES; may be overridden
    in company.default_account_codes JSON)."""
    from app.modules.companies.models import Company

    company = session.get(Company, company_id)
    overrides: dict[str, str] = {}
    if company and company.default_account_codes:
        overrides = __import__("json").loads(company.default_account_codes)
    return {role: overrides.get(role, code) for role, code in DEFAULT_ROLE_CODES.items()}


def post_journal_entry(
    session: Session,
    *,
    company_id: str,
    entry_date: date,
    source: SourceRef,
    lines: list[JournalLineSpec],
    description: str | None = None,
    actor_user_id: str | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    base_currency: str = "INR",
    allow_closed_period: bool = False,
) -> JournalEntry:
    """Create and post a balanced journal entry (the only posting path).

    `allow_closed_period` is a privileged escape hatch reserved for system
    lifecycle postings (year-end closing) that must land on the fiscal year's
    end date even after that month's period was closed by hand. The fiscal year
    itself must still exist and be open — only the per-month period check is
    skipped.
    """
    if not lines or len(lines) < 2:
        raise BusinessRuleError("JOURNAL_NEEDS_LINES", "A journal entry needs at least two lines")

    for line in lines:
        if line.side not in ("debit", "credit"):
            raise BusinessRuleError("JOURNAL_BAD_SIDE", f"Invalid line side '{line.side}'")
        if dec(line.amount_base) < 0:
            raise BusinessRuleError("JOURNAL_NEGATIVE_AMOUNT", "Journal line amounts must be >= 0")

    total_debit = sum((dec(l.amount_base) for l in lines if l.side == "debit"), Decimal("0"))
    total_credit = sum((dec(l.amount_base) for l in lines if l.side == "credit"), Decimal("0"))
    total_debit = money(total_debit, 2)
    total_credit = money(total_credit, 2)
    if total_debit != total_credit or total_debit == 0:
        raise BusinessRuleError(
            "JOURNAL_UNBALANCED",
            f"Debits ({total_debit}) do not equal credits ({total_credit})",
        )

    # Resolve (and validate) the posting period once, then snapshot the fiscal
    # year onto the entry so historical bucketing is stable even if the fiscal
    # year's date range is later edited.
    if allow_closed_period:
        fiscal_year = resolve_fiscal_year(session, company_id=company_id, on_date=entry_date)
        if fiscal_year is None:
            raise BusinessRuleError(
                "NO_FISCAL_YEAR", f"No fiscal year defined for {entry_date}"
            )
        if not fiscal_year.is_open:
            raise BusinessRuleError(
                "FISCAL_YEAR_CLOSED", f"Fiscal year {fiscal_year.name} is closed"
            )
    else:
        fiscal_year = ensure_period_open(session, company_id=company_id, on_date=entry_date)
    from app.core.config import get_settings

    rate = Decimal(str(exchange_rate)) if exchange_rate is not None else Decimal("1")
    if currency and currency != base_currency and exchange_rate is None:
        rate = Decimal(str(rate_for(session, company_id=company_id, from_currency=currency, base_currency=base_currency, on_date=entry_date)))

    doc_number = allocate_number(session, company_id, "journal_entry")
    entry = JournalEntry(
        company_id=company_id,
        fiscal_year_id=fiscal_year.id,
        doc_number=doc_number,
        entry_date=entry_date,
        description=description,
        status="posted",
        source_type=source.type,
        source_id=source.id,
        posted_at=datetime.now(timezone.utc),
        currency=currency or base_currency,
        exchange_rate=rate,
        created_by=actor_user_id,
    )
    session.add(entry)
    session.flush()

    codes = account_code_map(session, company_id)
    number = 1
    for spec in lines:
        account = get_account_by_code(session, company_id, spec.account_code)
        session.add(
            JournalLine(
                entry_id=entry.id,
                company_id=company_id,
                account_id=account.id,
                side=spec.side,
                amount=money(spec.amount_base, 2),
                doc_currency_amount=money(spec.doc_currency_amount if spec.doc_currency_amount is not None else spec.amount_base, 2),
                description=spec.description,
                party_ref=spec.party_ref,
                line_number=number,
            )
        )
        number += 1
    session.flush()
    return entry


def reverse_entry(
    session: Session, entry: JournalEntry, *, actor_user_id: str | None, entry_date: date | None = None
) -> JournalEntry:
    """Reversal entries mirror the original with sides swapped and link back."""
    if entry.status != "posted":
        raise BusinessRuleError("ENTRY_NOT_POSTED", "Only posted entries can be reversed")
    if entry.reversal_of_id is not None:
        raise BusinessRuleError("ALREADY_REVERSED", "This entry appears to be a reversal itself")
    if existing := session.scalar(
        select(JournalEntry.id).where(JournalEntry.reversal_of_id == entry.id)
    ):
        raise BusinessRuleError("ALREADY_REVERSED", "This entry has already been reversed")
    original_lines = session.execute(
        select(JournalLine).where(JournalLine.entry_id == entry.id).order_by(JournalLine.line_number)
    ).scalars().all()
    rev_date = entry_date or entry.entry_date
    specs = [
        JournalLineSpec(
            account_code=get_account(session, line.account_id, entry.company_id).code,
            side="credit" if line.side == "debit" else "debit",
            amount_base=line.amount,
            party_ref=line.party_ref,
            description=line.description,
            doc_currency_amount=line.doc_currency_amount,
        )
        for line in original_lines
    ]
    reversal = post_journal_entry(
        session,
        company_id=entry.company_id,
        entry_date=rev_date,
        source=SourceRef(type=entry.source_type, id=entry.source_id),
        lines=specs,
        description=f"Reversal of JE {entry.doc_number}",
        actor_user_id=actor_user_id,
        currency=entry.currency,
        exchange_rate=entry.exchange_rate,
    )
    reversal.reversal_of_id = entry.id
    session.flush()
    return reversal


def get_account(session: Session, account_id: str, company_id: str) -> Account:
    account = session.get(Account, account_id)
    if account is None or account.company_id != company_id:
        raise NotFoundError("Account")
    return account


def create_account(
    session: Session, *, company_id: str, code: str, name: str, account_type: str, normal_side: str
) -> Account:
    if account_type not in ACCOUNT_TYPE_ORDER:
        raise BusinessRuleError("BAD_ACCOUNT_TYPE", f"account_type must be one of {ACCOUNT_TYPE_ORDER}")
    if normal_side not in ("debit", "credit"):
        raise BusinessRuleError("BAD_NORMAL_SIDE", "normal_side must be debit or credit")
    if session.scalar(select(Account.id).where(Account.company_id == company_id, Account.code == code)):
        raise BusinessRuleError("ACCOUNT_CODE_TAKEN", f"Account code {code} already exists")
    account = Account(company_id=company_id, code=code, name=name, account_type=account_type, normal_side=normal_side)
    session.add(account)
    session.flush()
    return account


# ---- reports ----
def trial_balance(
    session: Session,
    company_id: str,
    *,
    from_date: date | None,
    to_date: date | None,
    fiscal_year_id: str | None = None,
    exclude_carry_forward: bool = False,
    exclude_closing: bool = False,
) -> list[dict]:
    """Aggregated account balances for a window.

    Carry-forward snapshots (`source_type == "carry_forward"`) re-state the
    pre-forward history inside the target year so a fiscal-year-scoped view
    shows opening balances. To avoid double-counting them against the
    originals they duplicate:
      * unbounded cumulative views (no ``from_date``, no FY filter) drop them;
      * date-ranged views admit them only when the window opens exactly on the
        snapshot's date (the year's first day);
      * fiscal-year-scoped views keep them — membership is that year's own
        entries, opening snapshot included.

    ``exclude_closing`` drops year-end closing entries (P&L → retained
    earnings) so income reports keep showing a closed year's real result;
    balance-sheet views keep them because that is where the profit lands.
    """
    stmt = (
        select(
            Account.code,
            Account.name,
            Account.account_type,
            JournalLine.side,
            func.sum(JournalLine.amount).label("total"),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "posted")
    )
    if from_date:
        stmt = stmt.where(JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(JournalEntry.entry_date <= to_date)
    if fiscal_year_id:
        stmt = stmt.where(JournalEntry.fiscal_year_id == fiscal_year_id)
    else:
        if from_date is None:
            stmt = stmt.where(JournalEntry.source_type != "carry_forward")
        else:
            stmt = stmt.where(
                or_(
                    JournalEntry.source_type != "carry_forward",
                    JournalEntry.entry_date == from_date,
                )
            )
    if exclude_carry_forward:
        stmt = stmt.where(JournalEntry.source_type != "carry_forward")
    if exclude_closing:
        stmt = stmt.where(JournalEntry.source_type != "year_end_close")
    stmt = stmt.group_by(Account.code, Account.name, Account.account_type, JournalLine.side).order_by(Account.code)
    balances: dict[tuple[str, str, str], dict[str, Decimal]] = {}
    for code, name, atype, side, total in session.execute(stmt):
        b = balances.setdefault((code, name, atype), {"debit": Decimal("0"), "credit": Decimal("0")})
        b[side] += dec(total)
    out = []
    for (code, name, atype), b in balances.items():
        signed = b["debit"] - b["credit"]
        out.append({
            "account_code": code,
            "account_name": name,
            "account_type": atype,
            "debit": b["debit"],
            "credit": b["credit"],
            "balance": signed,
        })
    return out


def general_ledger(
    session: Session,
    company_id: str,
    *,
    account_code: str | None,
    from_date: date | None,
    to_date: date | None,
    fiscal_year_id: str | None = None,
    limit: int = 500,
) -> list[dict]:
    stmt = (
        select(JournalLine, JournalEntry, Account)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "posted")
        .order_by(JournalEntry.entry_date, JournalLine.line_number)
        .limit(limit)
    )
    if account_code:
        stmt = stmt.where(Account.code == account_code)
    if from_date:
        stmt = stmt.where(JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(JournalEntry.entry_date <= to_date)
    if fiscal_year_id:
        stmt = stmt.where(JournalEntry.fiscal_year_id == fiscal_year_id)
    out = []
    for line, entry, account in session.execute(stmt):
        out.append({
            "entry_id": entry.id,
            "doc_number": entry.doc_number,
            "entry_date": entry.entry_date,
            "source_type": entry.source_type,
            "source_id": entry.source_id,
            "account_code": account.code,
            "account_name": account.name,
            "side": line.side,
            "amount": line.amount,
            "description": line.description,
            "party_ref": line.party_ref,
        })
    return out


def profit_and_loss(session: Session, company_id: str, *, from_date: date, to_date: date) -> dict:
    tb = trial_balance(
        session, company_id, from_date=from_date, to_date=to_date, exclude_closing=True
    )
    income = sum((abs(b["balance"]) for b in tb if b["account_type"] == "income"), Decimal("0"))
    expense = sum((b["balance"] for b in tb if b["account_type"] == "expense"), Decimal("0"))
    return {"from_date": from_date, "to_date": to_date, "income": income, "expense": expense, "profit": income - expense}


def balance_sheet(session: Session, company_id: str, *, as_of: date) -> dict:
    # Cumulative: carry-forward snapshots are excluded by the unbounded-view
    # rule (they duplicate pre-forward history already summed here).
    tb = trial_balance(session, company_id, from_date=None, to_date=as_of)
    assets = sum((b["balance"] for b in tb if b["account_type"] == "asset"), Decimal("0"))
    liabilities = sum((-b["balance"] for b in tb if b["account_type"] == "liability"), Decimal("0"))
    equity = sum((-b["balance"] for b in tb if b["account_type"] == "equity"), Decimal("0"))
    income = sum((-b["balance"] for b in tb if b["account_type"] == "income"), Decimal("0"))
    expense = sum((b["balance"] for b in tb if b["account_type"] == "expense"), Decimal("0"))
    retained = income - expense
    return {
        "as_of": as_of,
        "assets": assets,
        "liabilities": liabilities,
        "equity_before_retained": equity,
        "retained_earnings_period": retained,
        "equity_total": equity + retained,
        "check_liabilities_plus_equity": liabilities + equity + retained - assets,
    }
