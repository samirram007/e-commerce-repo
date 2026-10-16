"""Purchasing HTTP routes: POs, receipts, vendor bills."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_BILL_MANAGE, P_PURCHASE_APPROVE, P_PURCHASE_CREATE, P_PURCHASE_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.purchasing import service as svc
from app.modules.purchasing.models import GoodsReceiptLine, PurchaseOrderLine, VendorBillLine

router = APIRouter(prefix="/purchasing")


class POLineIn(BaseModel):
    product_id: str
    ordered_qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    uom_id: str | None = None
    tax_rate_id: str | None = None
    notes: str | None = None


class POCreateIn(BaseModel):
    vendor_id: str
    order_date: date
    expected_date: date | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = None
    lines: list[POLineIn] = Field(min_length=1)


class POOut(BaseModel):
    id: str
    doc_number: str
    vendor_id: str
    status: str
    order_date: date
    expected_date: date | None
    currency: str
    received_qty: Decimal
    approved_by: str | None


class ReceiveLineIn(BaseModel):
    order_line_id: str
    qty_received: Decimal = Field(gt=0)
    location_id: str
    batch_ref: str | None = None
    expiry_date: date | None = None


class ReceiveIn(BaseModel):
    lines: list[ReceiveLineIn] = Field(min_length=1)


class GRNOut(BaseModel):
    id: str
    doc_number: str
    order_id: str
    status: str
    received_at: str
    lines: list[dict]


class BillOut(BaseModel):
    id: str
    doc_number: str
    vendor_id: str
    status: str
    bill_date: date
    due_date: date | None
    currency: str
    total: Decimal
    total_base: Decimal


def _po_out(order) -> POOut:
    return POOut(
        id=order.id,
        doc_number=order.doc_number,
        vendor_id=order.vendor_id,
        status=order.status,
        order_date=order.order_date,
        expected_date=order.expected_date,
        currency=order.currency,
        received_qty=order.received_qty,
        approved_by=order.approved_by,
    )


def _grn_out(session: Session, receipt) -> GRNOut:
    lines = session.execute(select(GoodsReceiptLine).where(GoodsReceiptLine.receipt_id == receipt.id)).scalars().all()
    return GRNOut(
        id=receipt.id,
        doc_number=receipt.doc_number,
        order_id=receipt.order_id,
        status=receipt.status,
        received_at=receipt.received_at.isoformat(),
        lines=[
            {"id": l.id, "order_line_id": l.order_line_id, "product_id": l.product_id, "qty_received": str(l.qty_received), "unit_cost": str(l.unit_cost)}
            for l in lines
        ],
    )


def _bill_out(bill) -> BillOut:
    return BillOut(
        id=bill.id,
        doc_number=bill.doc_number,
        vendor_id=bill.vendor_id,
        status=bill.status,
        bill_date=bill.bill_date,
        due_date=bill.due_date,
        currency=bill.currency,
        total=bill.total,
        total_base=bill.total_base,
    )


@router.get("/orders", response_model=list[POOut])
def list_pos(
    status: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_PURCHASE_VIEW)),
    session: Session = Depends(get_db),
):
    from app.modules.purchasing.models import PurchaseOrder

    stmt = select(PurchaseOrder).where(PurchaseOrder.company_id == ctx.company_id).order_by(PurchaseOrder.order_date.desc())
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    return [_po_out(o) for o in session.execute(stmt).scalars().all()]


@router.get("/orders/{po_id}", response_model=POOut)
def get_po(po_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_VIEW)), session: Session = Depends(get_db)):
    return _po_out(svc.get_po(session, ctx.company_id, po_id))


@router.get("/orders/{po_id}/lines")
def get_po_lines(po_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_VIEW)), session: Session = Depends(get_db)):
    order = svc.get_po(session, ctx.company_id, po_id)
    lines = svc.get_po_lines(session, order.id)
    return [
        {"id": l.id, "product_id": l.product_id, "ordered_qty": str(l.ordered_qty), "received_qty": str(l.received_qty), "unit_cost": str(l.unit_cost), "tax_rate_id": l.tax_rate_id}
        for l in lines
    ]


@router.post("/orders", response_model=POOut, status_code=201)
def create_po(payload: POCreateIn, ctx: CompanyCtx = Depends(guard(P_PURCHASE_CREATE)), session: Session = Depends(get_db)):
    order = svc.create_po(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        vendor_id=payload.vendor_id,
        order_date=payload.order_date,
        expected_date=payload.expected_date,
        currency=payload.currency,
        notes=payload.notes,
        lines=[l.model_dump() for l in payload.lines],
    )
    log_action(session, action="po.created", entity_type="purchase_order", entity_id=order.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"doc_number": order.doc_number})
    return _po_out(order)


@router.post("/orders/{po_id}/submit", response_model=POOut)
def submit_po(po_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_CREATE)), session: Session = Depends(get_db)):
    order = svc.transition_po(session, ctx.company_id, po_id, "submitted", ctx.user.id)
    log_action(session, action="po.submitted", entity_type="purchase_order", entity_id=order.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _po_out(order)


@router.post("/orders/{po_id}/approve", response_model=POOut)
def approve_po(po_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_APPROVE)), session: Session = Depends(get_db)):
    order = svc.transition_po(session, ctx.company_id, po_id, "approved", ctx.user.id)
    log_action(session, action="po.approved", entity_type="purchase_order", entity_id=order.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _po_out(order)


@router.post("/orders/{po_id}/cancel", response_model=POOut)
def cancel_po(po_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_APPROVE)), session: Session = Depends(get_db)):
    order = svc.transition_po(session, ctx.company_id, po_id, "cancelled", ctx.user.id)
    log_action(session, action="po.cancelled", entity_type="purchase_order", entity_id=order.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _po_out(order)


@router.post("/orders/{po_id}/receive", response_model=GRNOut, status_code=201)
def receive_goods(po_id: str, payload: ReceiveIn, ctx: CompanyCtx = Depends(guard(P_BILL_MANAGE)), session: Session = Depends(get_db)):
    receipt = svc.receive_goods(
        session,
        company_id=ctx.company_id,
        po_id=po_id,
        actor_user_id=ctx.user.id,
        lines=[l.model_dump() for l in payload.lines],
    )
    log_action(session, action="grn.posted", entity_type="goods_receipt", entity_id=receipt.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"doc_number": receipt.doc_number})
    return _grn_out(session, receipt)


@router.post("/bills/from-receipt/{receipt_id}", response_model=BillOut, status_code=201)
def create_bill_from_receipt(
    receipt_id: str,
    bill_date: date,
    vendor_ref: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_BILL_MANAGE)),
    session: Session = Depends(get_db),
):
    bill = svc.create_bill_from_receipt(
        session, company_id=ctx.company_id, receipt_id=receipt_id, actor_user_id=ctx.user.id, bill_date=bill_date, vendor_ref=vendor_ref
    )
    log_action(session, action="vendor_bill.posted", entity_type="vendor_bill", entity_id=bill.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"total": str(bill.total)})
    return _bill_out(bill)


class AdhocBillLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = None
    qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    tax_percentage: Decimal = Decimal("0")
    expense_account_code: str | None = None


class AdhocBillIn(BaseModel):
    vendor_id: str
    bill_date: date
    currency: str = "USD"
    lines: list[AdhocBillLineIn] = Field(min_length=1)


@router.post("/bills", response_model=BillOut, status_code=201)
def create_bill_adhoc(payload: AdhocBillIn, ctx: CompanyCtx = Depends(guard(P_BILL_MANAGE)), session: Session = Depends(get_db)):
    bill = svc.create_bill_adhoc(
        session,
        company_id=ctx.company_id,
        vendor_id=payload.vendor_id,
        actor_user_id=ctx.user.id,
        bill_date=payload.bill_date,
        currency=payload.currency,
        lines=[l.model_dump() for l in payload.lines],
    )
    log_action(session, action="vendor_bill.posted", entity_type="vendor_bill", entity_id=bill.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"total": str(bill.total)})
    return _bill_out(bill)


@router.get("/bills", response_model=list[BillOut])
def list_bills(ctx: CompanyCtx = Depends(guard(P_PURCHASE_VIEW)), session: Session = Depends(get_db)):
    from app.modules.purchasing.models import VendorBill

    rows = session.execute(
        select(VendorBill).where(VendorBill.company_id == ctx.company_id).order_by(VendorBill.bill_date.desc())
    ).scalars().all()
    return [_bill_out(b) for b in rows]


@router.get("/bills/{bill_id}/lines")
def bill_lines(bill_id: str, ctx: CompanyCtx = Depends(guard(P_PURCHASE_VIEW)), session: Session = Depends(get_db)):
    from app.modules.purchasing.models import VendorBill

    bill = session.get(VendorBill, bill_id)
    if bill is None or bill.company_id != ctx.company_id:
        raise NotFoundError("Vendor bill")
    lines = session.execute(select(VendorBillLine).where(VendorBillLine.bill_id == bill.id)).scalars().all()
    return [
        {"id": l.id, "product_id": l.product_id, "qty": str(l.qty), "unit_cost": str(l.unit_cost), "line_total": str(l.line_total), "tax_amount": str(l.tax_amount)}
        for l in lines
    ]
