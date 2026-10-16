"""Storage location HTTP routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import P_INVENTORY_VIEW, P_STORAGE_MANAGE
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.storage import service as svc
from app.modules.storage.models import StorageLocation

router = APIRouter(prefix="/storage")


class LocationIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    location_type: str = "warehouse"
    parent_id: str | None = None
    address: str | None = None


class LocationOut(BaseModel):
    id: str
    code: str
    name: str
    location_type: str
    parent_id: str | None
    address: str | None
    is_active: bool


@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    location_type: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.list_locations(session, ctx.company_id, location_type=location_type)
    return [
        LocationOut(id=l.id, code=l.code, name=l.name, location_type=l.location_type, parent_id=l.parent_id, address=l.address, is_active=l.is_active)
        for l in rows
    ]


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(payload: LocationIn, ctx: CompanyCtx = Depends(guard(P_STORAGE_MANAGE)), session: Session = Depends(get_db)):
    loc = svc.create_location(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        code=payload.code,
        name=payload.name,
        location_type=payload.location_type,
        parent_id=payload.parent_id,
        address=payload.address,
    )
    log_action(session, action="storage.created", entity_type="storage_location", entity_id=loc.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"code": loc.code, "type": loc.location_type})
    return LocationOut(id=loc.id, code=loc.code, name=loc.name, location_type=loc.location_type, parent_id=loc.parent_id, address=loc.address, is_active=loc.is_active)
