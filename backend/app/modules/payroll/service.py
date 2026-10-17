"""Payroll service: employee master, payroll runs, payslips, GL posting.

Rules (invariants):
  * services never commit — the UoW (get_db) owns the single commit.
  * all money math goes through app.shared.money (Decimal only, HALF_UP cents).
  * one run per company/period (cancelled runs free the period for re-running).
  * posting the run is the only journal path: debit salaries expense (gross),
    credit withholdings payable + payroll payable (net split), via the
    centralized accounting.post_journal_entry pipeline.
"""
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.accounting.service import (
    JournalLineSpec,
    SourceRef,
    account_code_map,
    post_journal_entry,
)
from app.modules.payroll.models import (
    EMPLOYMENT_ACTIVE,
    RUN_CANCELLED,
    RUN_DRAFT,
    RUN_POSTED,
    Employee,
    Payslip,
    PayrollRun,
)
from app.shared.money import dec, money
from app.shared.numbering import allocate_number
from app.shared.pagination import ListParams, apply_list, paginate

# allowlists for the employees list endpoint (server-side search/sort)
EMPLOYEE_SEARCH_FIELDS = ("employee_code", "first_name", "last_name", "email", "department")
EMPLOYEE_SORTABLE_FIELDS = (
    "employee_code",
    "first_name",
    "last_name",
    "department",
    "employment_status",
    "base_salary",
    "allowances",
    "deduction_rate",
    "hire_date",
    "created_at",
)

# role -> (code, name, account_type, normal_side); created on demand for
# companies whose chart predates the payroll accounts.
PAYROLL_ACCOUNT_DEFAULTS: dict[str, tuple[str, str, str, str]] = {
    "salaries_expense": ("6100", "Salaries & Wages Expense", "expense", "debit"),
    "payroll_payable": ("2400", "Payroll Payable", "liability", "credit"),
    "withholdings_payable": ("2410", "Employee Withholdings Payable", "liability", "credit"),
}


# --------------------------------------------------------------------------
# employees
# --------------------------------------------------------------------------
def list_employees_page(
    session: Session, company_id: str, params: ListParams, employment_status: str | None = None
) -> tuple[list[Employee], int]:
    """Server-side paginated/searchable/sortable employee list."""
    stmt = select(Employee).where(Employee.company_id == company_id)
    if employment_status:
        stmt = stmt.where(Employee.employment_status == employment_status)
    stmt = apply_list(
        stmt,
        Employee,
        params,
        search_fields=EMPLOYEE_SEARCH_FIELDS,
        sortable_fields=EMPLOYEE_SORTABLE_FIELDS,
        default_sort=("employee_code", False),
    )
    return paginate(session, stmt, params)


def list_employees(
    session: Session, company_id: str, search: str | None = None, include_inactive: bool = True
) -> list[Employee]:
    stmt = select(Employee).where(Employee.company_id == company_id)
    if not include_inactive:
        stmt = stmt.where(Employee.employment_status == EMPLOYMENT_ACTIVE)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Employee.employee_code.ilike(like),
                Employee.first_name.ilike(like),
                Employee.last_name.ilike(like),
                Employee.email.ilike(like),
            )
        )
    return list(session.execute(stmt.order_by(Employee.employee_code)).scalars())


def get_employee(session: Session, company_id: str, employee_id: str) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None or employee.company_id != company_id:
        raise NotFoundError("Employee")
    return employee


def create_employee(session: Session, *, company_id: str, actor_user_id: str, data: dict) -> Employee:
    code = str(data["employee_code"]).strip()
    existing = session.scalar(
        select(Employee).where(Employee.company_id == company_id, Employee.employee_code == code)
    )
    if existing is not None:
        raise ConflictError(
            "PAYROLL_DUPLICATE_CODE", f"Employee code '{code}' already exists"
        )
    employee = Employee(
        company_id=company_id,
        employee_code=code,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data.get("email"),
        job_title=data.get("job_title"),
        department=data.get("department"),
        hire_date=data.get("hire_date"),
        employment_status=data.get("employment_status", EMPLOYMENT_ACTIVE),
        base_salary=money(data["base_salary"]),
        allowances=money(data.get("allowances", 0)),
        deduction_rate=dec(data.get("deduction_rate", 0)),
        created_by=actor_user_id,
        blamable=True,
    )
    session.add(employee)
    session.flush()
    return employee


def update_employee(session: Session, employee: Employee, data: dict) -> Employee:
    for field in (
        "first_name",
        "last_name",
        "email",
        "job_title",
        "department",
        "hire_date",
        "employment_status",
    ):
        if field in data and data[field] is not None:
            setattr(employee, field, data[field])
    if "base_salary" in data and data["base_salary"] is not None:
        employee.base_salary = money(data["base_salary"])
    if "allowances" in data and data["allowances"] is not None:
        employee.allowances = money(data["allowances"])
    if "deduction_rate" in data and data["deduction_rate"] is not None:
        employee.deduction_rate = dec(data["deduction_rate"])
    session.flush()
    return employee


# --------------------------------------------------------------------------
# calculation
# --------------------------------------------------------------------------
def calculate_payslip_amounts(employee: Employee) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (base, allowances, gross, deductions, net) — wait, 5-tuple.

    Kept as a helper so tests can assert the money rules in isolation:
      gross      = base + allowances
      deductions = gross * deduction_rate / 100   (HALF_UP cents)
      net        = gross - deductions
    """
    base = money(employee.base_salary)
    allowances = money(employee.allowances or 0)
    gross = money(base + allowances)
    deductions = money(gross * dec(employee.deduction_rate or 0) / Decimal(100))
    net = money(gross - deductions)
    return base, allowances, gross, deductions, net


def _validate_period(period_year: int, period_month: int) -> None:
    if not (2000 <= period_year <= 2100):
        raise BusinessRuleError("PAYROLL_BAD_PERIOD", f"Invalid period year {period_year}")
    if not (1 <= period_month <= 12):
        raise BusinessRuleError("PAYROLL_BAD_PERIOD", f"Invalid period month {period_month}")


# --------------------------------------------------------------------------
# payroll runs
# --------------------------------------------------------------------------
def list_runs(session: Session, company_id: str) -> list[PayrollRun]:
    stmt = (
        select(PayrollRun)
        .where(PayrollRun.company_id == company_id)
        .order_by(PayrollRun.period_year.desc(), PayrollRun.period_month.desc())
    )
    return list(session.execute(stmt).scalars())


def get_run(session: Session, company_id: str, run_id: str) -> PayrollRun:
    run = session.get(PayrollRun, run_id)
    if run is None or run.company_id != company_id:
        raise NotFoundError("Payroll run")
    return run


def run_payslips(session: Session, run: PayrollRun) -> list[Payslip]:
    stmt = select(Payslip).where(Payslip.run_id == run.id).order_by(Payslip.employee_code)
    return list(session.execute(stmt).scalars())


def run_payroll(
    session: Session, *, company_id: str, actor_user_id: str, period_year: int, period_month: int
) -> PayrollRun:
    """Create a draft payroll run + payslips for every active employee."""
    _validate_period(period_year, period_month)

    existing = session.scalar(
        select(PayrollRun).where(
            PayrollRun.company_id == company_id,
            PayrollRun.period_year == period_year,
            PayrollRun.period_month == period_month,
            PayrollRun.status != RUN_CANCELLED,
        )
    )
    if existing is not None:
        raise ConflictError(
            "PAYROLL_RUN_EXISTS",
            f"Payroll for {period_year}-{period_month:02d} already exists ({existing.doc_number})",
        )

    employees = list_employees(session, company_id, include_inactive=False)
    if not employees:
        raise BusinessRuleError("PAYROLL_NO_EMPLOYEES", "No active employees to pay")

    run = PayrollRun(
        company_id=company_id,
        period_year=period_year,
        period_month=period_month,
        doc_number=allocate_number(session, company_id, "payroll_run"),
        status=RUN_DRAFT,
        employee_count=len(employees),
        created_by=actor_user_id,
        blamable=True,
    )
    session.add(run)
    session.flush()

    total_gross = total_deductions = total_net = Decimal("0")
    for employee in employees:
        base, allowances, gross, deductions, net = calculate_payslip_amounts(employee)
        session.add(
            Payslip(
                company_id=company_id,
                run_id=run.id,
                employee_id=employee.id,
                period_year=period_year,
                period_month=period_month,
                employee_code=employee.employee_code,
                employee_name=f"{employee.first_name} {employee.last_name}".strip(),
                status=RUN_DRAFT,
                base_salary=base,
                allowances=allowances,
                gross=gross,
                deduction_rate=dec(employee.deduction_rate or 0),
                deductions=deductions,
                net_pay=net,
                created_by=actor_user_id,
                blamable=True,
            )
        )
        total_gross += gross
        total_deductions += deductions
        total_net += net

    run.total_gross = money(total_gross)
    run.total_deductions = money(total_deductions)
    run.total_net = money(total_net)
    session.flush()
    return run


def _ensure_payroll_accounts(session: Session, company_id: str) -> dict[str, str]:
    """Resolve payroll account codes and create any missing chart accounts.

    Companies seeded before payroll existed lack 6100/2400/2410 — create them
    on first posting so the GL split never fails with NOT_FOUND.
    """
    from app.modules.accounting.models import Account

    codes = account_code_map(session, company_id)
    for role, (default_code, name, account_type, _side) in PAYROLL_ACCOUNT_DEFAULTS.items():
        code = codes.get(role, default_code)
        exists = session.scalar(
            select(Account.id).where(Account.company_id == company_id, Account.code == code)
        )
        if exists is None:
            session.add(
                Account(
                    company_id=company_id,
                    code=code,
                    name=name,
                    account_type=account_type,
                    normal_side=_side,
                    is_system=True,
                )
            )
        session.flush()
        codes[role] = code
    return codes


def post_payroll_run(
    session: Session, *, company_id: str, run_id: str, actor_user_id: str
) -> PayrollRun:
    """Post a draft run: one balanced journal entry via the accounting pipeline."""
    run = get_run(session, company_id, run_id)
    if run.status != RUN_DRAFT:
        raise ConflictError(
            "PAYROLL_RUN_NOT_DRAFT", f"Payroll run {run.doc_number} is {run.status}"
        )

    # totals are recomputed from the (immutable) payslips, never trusted from input
    payslips = run_payslips(session, run)
    if not payslips:
        raise BusinessRuleError("PAYROLL_EMPTY_RUN", "Payroll run has no payslips")

    total_gross = money(sum((dec(p.gross) for p in payslips), Decimal("0")))
    total_deductions = money(sum((dec(p.deductions) for p in payslips), Decimal("0")))
    total_net = money(sum((dec(p.net_pay) for p in payslips), Decimal("0")))
    if total_gross <= 0:
        raise BusinessRuleError("PAYROLL_EMPTY_RUN", "Payroll gross total must be positive")

    codes = _ensure_payroll_accounts(session, company_id)

    from app.modules.companies.models import Company

    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")

    entry_date = date(
        run.period_year, run.period_month, calendar.monthrange(run.period_year, run.period_month)[1]
    )
    lines = [
        JournalLineSpec(
            account_code=codes["salaries_expense"],
            side="debit",
            amount_base=total_gross,
            description=f"Payroll {run.period_year}-{run.period_month:02d}",
        )
    ]
    if total_deductions > 0:
        lines.append(
            JournalLineSpec(
                account_code=codes["withholdings_payable"],
                side="credit",
                amount_base=total_deductions,
                description=f"Withholdings {run.period_year}-{run.period_month:02d}",
            )
        )
    if total_net > 0:
        lines.append(
            JournalLineSpec(
                account_code=codes["payroll_payable"],
                side="credit",
                amount_base=total_net,
                description=f"Net pay payable {run.period_year}-{run.period_month:02d}",
            )
        )

    entry = post_journal_entry(
        session,
        company_id=company_id,
        entry_date=entry_date,
        source=SourceRef(type="payroll_run", id=run.id),
        lines=lines,
        description=f"Payroll {run.period_year}-{run.period_month:02d} ({len(payslips)} employees)",
        actor_user_id=actor_user_id,
        currency=company.base_currency,
        base_currency=company.base_currency,
    )

    run.status = RUN_POSTED
    run.journal_entry_id = entry.id
    run.posted_at = datetime.now(timezone.utc)
    run.total_gross = total_gross
    run.total_deductions = total_deductions
    run.total_net = total_net
    for slip in payslips:
        slip.status = RUN_POSTED
    session.flush()
    return run


def cancel_payroll_run(
    session: Session, *, company_id: str, run_id: str, actor_user_id: str
) -> PayrollRun:
    """Cancel a draft run (posted runs must be reversed through accounting)."""
    run = get_run(session, company_id, run_id)
    if run.status == RUN_POSTED:
        raise ConflictError(
            "PAYROLL_RUN_POSTED",
            f"Payroll run {run.doc_number} is posted; reverse the journal entry instead",
        )
    if run.status == RUN_CANCELLED:
        raise ConflictError(
            "PAYROLL_RUN_CANCELLED", f"Payroll run {run.doc_number} is already cancelled"
        )
    run.status = RUN_CANCELLED
    for slip in run_payslips(session, run):
        slip.status = RUN_CANCELLED
    session.flush()
    return run
