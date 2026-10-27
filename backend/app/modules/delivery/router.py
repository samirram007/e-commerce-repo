"""Shipping carrier routes: the admin panel's view of third-party carriers."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import P_CARRIERS_MANAGE, P_CARRIERS_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.delivery import profiles as svc
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/delivery")


class CarrierIn(BaseModel):
    """Admin panel payload for one carrier.

    `credentials` is write-only (a blank value keeps the stored secret);
    `settings` carries any extra key/values the carrier integration needs.
    """

    is_enabled: bool | None = None
    priority: int | None = None
    label: str | None = Field(default=None, max_length=80)
    credentials: dict[str, str] | None = None
    settings: dict | None = None
    notes: str | None = None


@router.get("/carriers")
def list_carriers(
    ctx: CompanyCtx = Depends(guard(P_CARRIERS_VIEW)), session: Session = Depends(get_db)
):
    """The carrier catalog plus this company's configuration for each one."""
    return {"carriers": svc.carrier_catalog(), "profiles": svc.overview(session, ctx.company_id)}


@router.put("/carriers/{carrier}")
def save_carrier(
    carrier: str,
    payload: CarrierIn,
    ctx: CompanyCtx = Depends(guard(P_CARRIERS_MANAGE)),
    session: Session = Depends(get_db),
):
    """Enable/disable a carrier and store its credentials."""
    row = svc.save(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        carrier=carrier,
        payload=payload.model_dump(exclude_unset=True),
    )
    log_action(
        session,
        action="shipping.carrier.updated",
        entity_type="carrier_profile",
        entity_id=row.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={"carrier": row.carrier, "enabled": row.is_enabled},
    )
    return next(entry for entry in svc.overview(session, ctx.company_id) if entry["carrier"] == carrier)


@router.delete("/carriers/{carrier}")
def delete_carrier(
    carrier: str,
    ctx: CompanyCtx = Depends(guard(P_CARRIERS_MANAGE)),
    session: Session = Depends(get_db),
):
    """Drop a company's configuration for a carrier (stored secrets included)."""
    svc.remove(session, ctx.company_id, carrier)
    log_action(
        session,
        action="shipping.carrier.removed",
        entity_type="carrier_profile",
        entity_id=carrier,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
    )
    return {"deleted": carrier}
