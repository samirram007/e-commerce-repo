"""Pydantic schemas for identity endpoints."""
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- requests ----
class RegisterAdminIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=200)
    is_platform_admin: bool = False
    # Optional single-step setup: grant the new user a role in a company.
    company_id: str | None = None
    role_names: list[str] = Field(default_factory=list)
    is_company_admin: bool = False


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    is_platform_admin: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class RoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    permissions: list[str] = Field(default_factory=list)


# ---- responses ----
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_platform_admin: bool
    is_active: bool
    # Union of the user's role names across companies (informational).
    roles: list[str] = Field(default_factory=list)


class CompanySummary(BaseModel):
    id: str
    name: str
    base_currency: str


class MeOut(BaseModel):
    user: UserOut
    companies: list[CompanySummary]
    permissions: list[str]
    is_company_admin: bool
    roles: list[str] = Field(default_factory=list)


class LoginOut(BaseModel):
    access_token: str
    expires_in: int
    user: UserOut


class RoleOut(BaseModel):
    id: str
    name: str
    label: str = ""
    permissions: list[str]
    is_system: bool
