"""Payments HTTP routes: manual receipts/vouchers, allocations, refunds."""
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import P_PAYMENTS_MANAGE, P_PAYMENTS_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.payments import service as svc
from app.modules.payments.models import PaymentAllocation, PaymentRecord

router = APIRouter(prefix="/payments")


class AllocationIn(BaseModel):
    document_type: str
    document_id: str
    amount: Decimal = Field(gt=0)


class PaymentIn(BaseModel):
    direction: str = "receipt"
    method: str = "bank"
    party_type: str | None = None
    party_id: str | None = None
    amount: Decimal = Field(gt=0)
    occurred_at: date
    notes: str | None = None
    allocations: list[AllocationIn] | None = None


class RefundIn(BaseModel):
    original_payment_id: str
    amount: Decimal = Field(gt=0)


class PaymentOut(BaseModel):
    id: str
    direction: str
    provider: str
    provider_ref: str | None
    mode: str | None = None
    method: str
    status: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    order_id: str | None

def _out(r: PaymentRecord) -> PaymentOut:
    return PaymentOut(
        id=r.id, direction=r.direction, provider=r.provider, provider_ref=r.provider_ref,
        mode=r.mode, method=r.method, status=r.status, amount=r.amount, currency=r.currency,
        occurred_at=r.occurred_at, order_id=r.order_id,
    )


@router.get("", response_model=list[PaymentOut])
def list_payments(ctx: CompanyCtx = Depends(guard(P_PAYMENTS_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(PaymentRecord).where(PaymentRecord.company_id == ctx.company_id).order_by(PaymentRecord.occurred_at.desc()).limit(500)
    ).scalars().all()
    return [_out(r) for r in rows]


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(
    payload: PaymentIn,
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    record = svc.create_manual_payment(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        direction=payload.direction,
        method=payload.method,
        party_type=payload.party_type,
        party_id=payload.party_id,
        amount=payload.amount,
        occurred_at=payload.occurred_at,
        allocations=[a.model_dump() for a in payload.allocations] if payload.allocations else None,
        notes=payload.notes,
    )
    log_action(session, action="payment.recorded", entity_type="payment_record", entity_id=record.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"ref": record.provider_ref, "amount": str(record.amount)})
    return _out(record)


@router.post("/allocate", status_code=201)
def allocate(
    payment_id: str,
    allocations: list[AllocationIn],
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    rows = svc.allocate_payment(
        session, ctx.company_id, payment_id, [a.model_dump() for a in allocations], ctx.user.id
    )
    log_action(session, action="payment.allocated", entity_type="payment_record", entity_id=payment_id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return [{"id": r.id, "document_id": r.document_id, "amount": str(r.amount)} for r in rows]


@router.get("/{payment_id}/allocations")
def get_allocations(payment_id: str, ctx: CompanyCtx = Depends(guard(P_PAYMENTS_VIEW)), session: Session = Depends(get_db)):
    payment = session.get(PaymentRecord, payment_id)
    if payment is None or payment.company_id != ctx.company_id:
        raise NotFoundError("Payment")
    rows = session.execute(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)).scalars().all()
    return [
        {"id": a.id, "document_type": a.document_type, "document_id": a.document_id, "amount": str(a.amount)}
        for a in rows
    ]
