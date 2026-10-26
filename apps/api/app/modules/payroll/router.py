"""Payroll HTTP routes: employees, payroll runs, payslips."""
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.permissions import P_PAYROLL_MANAGE, P_PAYROLL_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.payroll import service as svc
from app.modules.payroll.models import Employee, Payslip, PayrollRun
from app.shared.pagination import ListParams, Page

router = APIRouter(prefix="/payroll")


# ---- employee schemas ----
class EmployeeIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=32)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    employment_status: str = "active"
    base_salary: Decimal = Field(gt=0)
    allowances: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class EmployeeUpdateIn(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    employment_status: str | None = None
    base_salary: Decimal | None = Field(default=None, gt=0)
    allowances: Decimal | None = Field(default=None, ge=0)
    deduction_rate: Decimal | None = Field(default=None, ge=0, le=100)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_code: str
    first_name: str
    last_name: str
    email: str | None
    job_title: str | None
    department: str | None
    hire_date: date | None
    employment_status: str
    base_salary: Decimal
    allowances: Decimal
    deduction_rate: Decimal


# ---- payroll run schemas ----
class RunIn(BaseModel):
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)


class PayslipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_id: str
    employee_code: str
    employee_name: str
    status: str
    base_salary: Decimal
    allowances: Decimal
    gross: Decimal
    deduction_rate: Decimal
    deductions: Decimal
    net_pay: Decimal


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_number: str
    period_year: int
    period_month: int
    status: str
    employee_count: int
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
    journal_entry_id: str | None
    posted_at: datetime | None


class RunDetailOut(RunOut):
    payslips: list[PayslipOut] = []


# ---- employees ----
@router.get("/employees", response_model=Page[EmployeeOut])
def list_employees(
    employment_status: str | None = Query(None, max_length=16),
    params: ListParams = Depends(),
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_VIEW)),
    session: Session = Depends(get_db),
):
    rows, total = svc.list_employees_page(
        session, ctx.company_id, params, employment_status=employment_status
    )
    return Page[EmployeeOut](
        items=[EmployeeOut.model_validate(e) for e in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(
    payload: EmployeeIn,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_MANAGE)),
    session: Session = Depends(get_db),
):
    employee = svc.create_employee(
        session, company_id=ctx.company_id, actor_user_id=ctx.user.id, data=payload.model_dump()
    )
    log_action(
        session,
        action="payroll.employee.created",
        entity_type="payroll_employee",
        entity_id=employee.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={"employee_code": employee.employee_code},
    )
    return EmployeeOut.model_validate(employee)


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_VIEW)),
    session: Session = Depends(get_db),
):
    return EmployeeOut.model_validate(svc.get_employee(session, ctx.company_id, employee_id))


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    payload: EmployeeUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_MANAGE)),
    session: Session = Depends(get_db),
):
    employee = svc.get_employee(session, ctx.company_id, employee_id)
    employee = svc.update_employee(session, employee, payload.model_dump(exclude_unset=True))
    log_action(
        session,
        action="payroll.employee.updated",
        entity_type="payroll_employee",
        entity_id=employee.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
    )
    return EmployeeOut.model_validate(employee)


# ---- payroll runs ----
def _run_detail(run: PayrollRun, payslips: list[Payslip]) -> RunDetailOut:
    detail = RunDetailOut.model_validate(run)
    detail.payslips = [PayslipOut.model_validate(p) for p in payslips]
    return detail


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_VIEW)), session: Session = Depends(get_db)
):
    return [RunOut.model_validate(r) for r in svc.list_runs(session, ctx.company_id)]


@router.post("/runs", response_model=RunDetailOut, status_code=201)
def create_run(
    payload: RunIn,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_MANAGE)),
    session: Session = Depends(get_db),
):
    run = svc.run_payroll(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        period_year=payload.period_year,
        period_month=payload.period_month,
    )
    log_action(
        session,
        action="payroll.run.created",
        entity_type="payroll_run",
        entity_id=run.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={"doc_number": run.doc_number},
    )
    return _run_detail(run, svc.run_payslips(session, run))


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def get_run(
    run_id: str,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_VIEW)),
    session: Session = Depends(get_db),
):
    run = svc.get_run(session, ctx.company_id, run_id)
    return _run_detail(run, svc.run_payslips(session, run))


@router.post("/runs/{run_id}/post", response_model=RunDetailOut, status_code=201)
def post_run(
    run_id: str,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_MANAGE)),
    session: Session = Depends(get_db),
):
    run = svc.post_payroll_run(
        session, company_id=ctx.company_id, run_id=run_id, actor_user_id=ctx.user.id
    )
    log_action(
        session,
        action="payroll.run.posted",
        entity_type="payroll_run",
        entity_id=run.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={"doc_number": run.doc_number, "journal_entry_id": run.journal_entry_id},
    )
    return _run_detail(run, svc.run_payslips(session, run))


@router.post("/runs/{run_id}/cancel", response_model=RunDetailOut)
def cancel_run(
    run_id: str,
    ctx: CompanyCtx = Depends(guard(P_PAYROLL_MANAGE)),
    session: Session = Depends(get_db),
):
    run = svc.cancel_payroll_run(
        session, company_id=ctx.company_id, run_id=run_id, actor_user_id=ctx.user.id
    )
    log_action(
        session,
        action="payroll.run.cancelled",
        entity_type="payroll_run",
        entity_id=run.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
    )
    return _run_detail(run, svc.run_payslips(session, run))
