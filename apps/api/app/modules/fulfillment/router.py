"""Fulfillment HTTP routes + carrier webhook endpoint."""
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import P_SALES_FULFILL, P_SALES_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.fulfillment import service as svc
from app.modules.fulfillment.models import Shipment
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/shipments")


@router.get("", response_model=list[dict])
def list_shipments(
    status: str | None = None,
    order_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_SALES_VIEW)),
    session: Session = Depends(get_db),
):
    stmt = select(Shipment).where(Shipment.company_id == ctx.company_id).order_by(Shipment.created_at.desc())
    if status:
        stmt = stmt.where(Shipment.status == status)
    if order_id:
        stmt = stmt.where(Shipment.order_id == order_id)
    return [_shipment_brief(s) for s in session.execute(stmt).scalars().all()]


@router.get("/{shipment_id}")
def get_shipment(shipment_id: str, ctx: CompanyCtx = Depends(guard(P_SALES_VIEW)), session: Session = Depends(get_db)):
    shipment = svc.get_shipment(session, ctx.company_id, shipment_id)
    lines = svc.get_shipment_lines(session, shipment.id)
    data = _shipment_brief(shipment)
    data["lines"] = [
        {"id": l.id, "order_line_id": l.order_line_id, "product_id": l.product_id, "from_location_id": l.from_location_id, "qty": str(l.qty)}
        for l in lines
    ]
    return data


@router.post("", status_code=201)
def create_shipment(
    order_id: str,
    ctx: CompanyCtx = Depends(guard(P_SALES_FULFILL)),
    session: Session = Depends(get_db),
):
    shipment = svc.create_shipment(session, company_id=ctx.company_id, actor_user_id=ctx.user.id, order_id=order_id)
    log_action(session, action="shipment.created", entity_type="shipment", entity_id=shipment.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"doc_number": shipment.doc_number})
    return _shipment_brief(shipment)


@router.post("/{shipment_id}/transition")
def transition(shipment_id: str, to_status: str, ctx: CompanyCtx = Depends(guard(P_SALES_FULFILL)), session: Session = Depends(get_db)):
    shipment = svc.transition_shipment(session, ctx.company_id, shipment_id, to_status, ctx.user.id)
    log_action(session, action="shipment.transition", entity_type="shipment", entity_id=shipment.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"status": shipment.status})
    return _shipment_brief(shipment)


@router.post("/{shipment_id}/dispatch")
def dispatch(
    shipment_id: str,
    carrier: str = "mock",
    ctx: CompanyCtx = Depends(guard(P_SALES_FULFILL)),
    session: Session = Depends(get_db),
):
    shipment = svc.get_shipment(session, ctx.company_id, shipment_id)
    shipment = svc.carrier_dispatch(session, shipment, carrier_name=carrier, actor_user_id=ctx.user.id)
    log_action(session, action="shipment.dispatched", entity_type="shipment", entity_id=shipment.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"tracking": shipment.tracking_number})
    return _shipment_brief(shipment)


@router.post("/{shipment_id}/pod", status_code=200)
def upload_pod(shipment_id: str, ctx: CompanyCtx = Depends(guard(P_SALES_FULFILL)), session: Session = Depends(get_db)):
    shipment = svc.get_shipment(session, ctx.company_id, shipment_id)
    log_action(session, action="shipment.pod", entity_type="shipment", entity_id=shipment.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return {"id": shipment.id, "status": shipment.status}


class CarrierWebhookIn(BaseModel):
    tracking_number: str
    event_id: str | None = None
    event: str = "delivered"


@router.post("/webhook/delivery")
def carrier_webhook(
    payload: CarrierWebhookIn,
    x_signature: str = Header(default="", alias="X-Signature"),
    company_id: str | None = Header(default=None, alias="X-Company-Id"),
    session: Session = Depends(get_db),
):
    if not company_id:
        raise BusinessRuleError("COMPANY_REQUIRED", "Webhook needs X-Company-Id header")
    body = {"tracking_number": payload.tracking_number, "event": payload.event, "event_id": payload.event_id}
    shipment = svc.confirm_carrier_delivery(
        session, company_id=company_id, tracking_number=payload.tracking_number, signature=x_signature, payload=body
    )
    return {"id": shipment.id, "status": shipment.status}


def _shipment_brief(shipment: Shipment) -> dict:
    return {
        "id": shipment.id,
        "doc_number": shipment.doc_number,
        "order_id": shipment.order_id,
        "status": shipment.status,
        "carrier": shipment.carrier_name,
        "tracking_number": shipment.tracking_number,
        "dispatched_at": shipment.dispatched_at.isoformat() if shipment.dispatched_at else None,
        "delivered_at": shipment.delivered_at.isoformat() if shipment.delivered_at else None,
        "shipping_address": shipment.shipping_address_snapshot,
    }
