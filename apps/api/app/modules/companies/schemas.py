"""Pydantic schemas for company endpoints."""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    legal_name: str = Field(default="", max_length=200)
    base_currency: str = Field(default="INR", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=64)
    locale: str = Field(default="en-IN", max_length=16)
    address: str | None = None
    tax_identifier: str | None = Field(default=None, max_length=64)


class CompanyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = None
    timezone: str | None = None
    locale: str | None = None
    address: str | None = None
    tax_identifier: str | None = None
    allow_negative_stock: bool | None = None
    allow_guest_checkout: bool | None = None
    is_active: bool | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    legal_name: str
    base_currency: str
    timezone: str
    locale: str
    address: str | None
    tax_identifier: str | None
    allow_negative_stock: bool
    allow_guest_checkout: bool
    is_active: bool


class MemberCreateIn(BaseModel):
    user_id: str
    is_company_admin: bool = False
    role_names: list[str] = Field(default_factory=list)


class MemberUpdateIn(BaseModel):
    is_company_admin: bool | None = None
    role_names: list[str] | None = None


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str | None = None
    is_company_admin: bool
    role_names: list[str]


class ExchangeRateIn(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(gt=0)
