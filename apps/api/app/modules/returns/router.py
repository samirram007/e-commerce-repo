"""Returns HTTP routes."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import P_RETURNS_MANAGE
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.returns import service as svc
from app.modules.returns.models import SalesReturn

router = APIRouter(prefix="/returns")


class ReturnLineIn(BaseModel):
    order_line_id: str
    qty: Decimal = Field(gt=0)
    disposition: str = "resalable"
    restock_location_id: str | None = None


class ReturnCreateIn(BaseModel):
    order_id: str
    notes: str | None = None
    lines: list[ReturnLineIn] = Field(min_length=1)


class ReturnOut(BaseModel):
    id: str
    doc_number: str
    order_id: str
    invoice_id: str | None
    customer_id: str
    status: str
    credit_note_id: str | None
    refund_payment_id: str | None


def _out(row: SalesReturn) -> ReturnOut:
    return ReturnOut(
        id=row.id, doc_number=row.doc_number, order_id=row.order_id,
        invoice_id=row.invoice_id, customer_id=row.customer_id, status=row.status,
        credit_note_id=row.credit_note_id, refund_payment_id=row.refund_payment_id,
    )


@router.post("", response_model=ReturnOut, status_code=201)
def create_return(payload: ReturnCreateIn, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    row = svc.create_sales_return(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        order_id=payload.order_id,
        lines=[l.model_dump() for l in payload.lines],
        notes=payload.notes,
    )
    log_action(session, action="sales_return.requested", entity_type="sales_return", entity_id=row.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _out(row)


@router.get("", response_model=list[ReturnOut])
def list_returns(status: str | None = None, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    stmt = select(SalesReturn).where(SalesReturn.company_id == ctx.company_id).order_by(SalesReturn.requested_at.desc())
    if status:
        stmt = stmt.where(SalesReturn.status == status)
    return [_out(r) for r in session.execute(stmt).scalars().all()]


@router.get("/{return_id}")
def get_return(return_id: str, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    row = svc.get_return(session, ctx.company_id, return_id)
    lines = svc.return_lines(session, row.id)
    data = _out(row).model_dump()
    data["lines"] = [
        {"id": l.id, "order_line_id": l.order_line_id, "product_id": l.product_id, "qty": str(l.qty), "unit_price": str(l.unit_price), "disposition": l.disposition}
        for l in lines
    ]
    return data


@router.post("/{return_id}/approve", response_model=ReturnOut)
def approve(return_id: str, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    row = svc.get_return(session, ctx.company_id, return_id)
    row = svc.approve_return(session, row, ctx.user.id)
    log_action(session, action="sales_return.approved", entity_type="sales_return", entity_id=row.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _out(row)


@router.post("/{return_id}/reject", response_model=ReturnOut)
def reject(return_id: str, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    row = svc.get_return(session, ctx.company_id, return_id)
    row = svc.reject_return(session, row, ctx.user.id)
    log_action(session, action="sales_return.rejected", entity_type="sales_return", entity_id=row.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _out(row)


@router.post("/{return_id}/complete", response_model=ReturnOut)
def complete(return_id: str, ctx: CompanyCtx = Depends(guard(P_RETURNS_MANAGE)), session: Session = Depends(get_db)):
    row = svc.get_return(session, ctx.company_id, return_id)
    row = svc.complete_return(session, row, actor_user_id=ctx.user.id)
    log_action(session, action="sales_return.completed", entity_type="sales_return", entity_id=row.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"credit_note": row.credit_note_id, "refund": row.refund_payment_id})
    return _out(row)
