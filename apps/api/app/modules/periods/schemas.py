"""Period context / reporting period schemas."""
from datetime import date

from pydantic import BaseModel, Field


class ReportingPeriodIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date


class ReportingPeriodUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    start_date: date | None = None
    end_date: date | None = None


class ReportingPeriodOut(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date


class FiscalYearOption(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date
    is_open: bool


class AccountingPeriodOption(BaseModel):
    id: str
    fiscal_year_id: str
    start_date: date
    end_date: date
    is_open: bool


class PeriodContextIn(BaseModel):
    fiscal_year_id: str | None = None
    accounting_period_id: str | None = None
    reporting_period_id: str | None = None


class PeriodContextOut(BaseModel):
    fiscal_year: FiscalYearOption | None = None
    accounting_period: AccountingPeriodOption | None = None
    reporting_period: ReportingPeriodOut | None = None
    # Resolved inclusive date window used to scope reads (reporting → accounting → FY).
    effective_from: date | None = None
    effective_to: date | None = None
