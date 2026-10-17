"""Payroll domain models: employees, payroll runs, payslips.

All monetary values are NUMERIC(14,2) — never float (see AGENT.md §6).
Deductions are expressed as an employee-level percentage withheld from gross
pay (tax/insurance); the run's GL posting splits net pay and withholdings.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

EMPLOYMENT_ACTIVE = "active"
EMPLOYMENT_INACTIVE = "inactive"
EMPLOYMENT_STATUSES = (EMPLOYMENT_ACTIVE, EMPLOYMENT_INACTIVE)

RUN_DRAFT = "draft"
RUN_POSTED = "posted"
RUN_CANCELLED = "cancelled"
RUN_STATUSES = (RUN_DRAFT, RUN_POSTED, RUN_CANCELLED)


class Employee(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "payroll_employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EMPLOYMENT_ACTIVE
    )
    # monthly gross components (company base currency)
    base_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    allowances: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # percentage withheld from gross (e.g. 10.00 = 10%), 0..100
    deduction_rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_payroll_employees_code"),
    )


class PayrollRun(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "payroll_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12
    doc_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RUN_DRAFT)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_net: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "doc_number", name="uq_payroll_runs_doc_number"),
    )


class Payslip(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "payroll_payslips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    # snapshots so payslips stay stable if the employee record changes later
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_name: Mapped[str] = mapped_column(String(210), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RUN_DRAFT)
    base_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    allowances: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    deduction_rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
