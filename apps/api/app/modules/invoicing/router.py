"""Invoicing HTTP routes: invoices, credit notes, AR aging."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import P_INVOICES_MANAGE, P_INVOICES_VIEW
from app.core.security import new_id
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.invoicing import service as svc
from app.modules.invoicing.models import CreditNote, CustomerInvoice, InvoiceLine
from app.shared.money import dec, money

router = APIRouter(prefix="/invoices")


class InvoiceLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = None
    qty: Decimal = Field(gt=0)
    unit_price: Decimal | None = None
    discount: Decimal = Decimal("0")
    tax_rate_id: str | None = None
    tax_percentage: Decimal = Decimal("0")


class InvoiceCreateIn(BaseModel):
    customer_id: str
    invoice_date: date
    # buyer address snapshot for the printed GST invoice
    customer_address: str | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    shipping_total: Decimal = Decimal("0")
    # order-level manual discount, spread across the lines by value
    discount: Decimal = Decimal("0")
    due_date: date | None = None
    notes: str | None = None
    order_id: str | None = None
    post: bool = True
    lines: list[InvoiceLineIn] = Field(min_length=1)


class InvoiceLineOut(BaseModel):
    id: str
    product_id: str | None
    sku_snapshot: str
    hsn_sac: str | None
    description_snapshot: str
    qty: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_percentage: Decimal
    line_total: Decimal
    tax_amount: Decimal


class TaxBreakupOut(BaseModel):
    """Tax charged at one GST rate; the UI shows CGST/SGST halves in the label.

    `taxable` is the value the rate applies to, so a printable invoice can show
    the taxable value and the CGST/SGST split per slab.
    """

    rate: Decimal
    taxable: Decimal
    amount: Decimal


class InvoiceOut(BaseModel):
    id: str
    doc_number: str
    customer_id: str
    customer_name: str
    customer_address: str | None
    customer_tax_identifier: str | None
    status: str
    invoice_date: date
    due_date: date | None
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    total: Decimal
    total_base: Decimal
    order_id: str | None
    tax_breakup: list[TaxBreakupOut] = Field(default_factory=list)


class CreditNoteIn(BaseModel):
    invoice_id: str
    note_date: date
    reason: str | None = None
    restock: bool = False
    restock_location_id: str | None = None
    lines: list["CreditLineIn"] = Field(min_length=1)


class CreditLineIn(BaseModel):
    invoice_line_id: str | None = None
    description: str | None = None
    qty: Decimal = Field(gt=0)
    unit_price: Decimal | None = None
    tax_amount: Decimal | None = None


def _breakup_map(session: Session, invoice_ids: list[str]) -> dict[str, list[TaxBreakupOut]]:
    """Tax per GST rate for each invoice, in one grouped query (no N+1)."""
    if not invoice_ids:
        return {}
    rows = session.execute(
        select(
            InvoiceLine.invoice_id,
            InvoiceLine.tax_percentage,
            func.sum(InvoiceLine.tax_amount),
            func.sum(InvoiceLine.qty * InvoiceLine.unit_price - InvoiceLine.discount),
        )
        .where(InvoiceLine.invoice_id.in_(invoice_ids))
        .group_by(InvoiceLine.invoice_id, InvoiceLine.tax_percentage)
    ).all()
    out: dict[str, list[TaxBreakupOut]] = {}
    for invoice_id, rate, amount, taxable in rows:
        # zero-rated (exempt) lines contribute nothing to the tax total
        if dec(rate) <= 0:
            continue
        out.setdefault(invoice_id, []).append(
            TaxBreakupOut(
                rate=dec(rate),
                taxable=money(dec(taxable), 2),
                amount=money(dec(amount), 2),
            )
        )
    for values in out.values():
        values.sort(key=lambda row: row.rate)
    return out


def _invoice_out(invoice: CustomerInvoice, breakup: list[TaxBreakupOut] | None = None) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        doc_number=invoice.doc_number,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name,
        customer_address=invoice.customer_address,
        customer_tax_identifier=invoice.customer_tax_identifier,
        status=invoice.status,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        discount_total=invoice.discount_total,
        tax_total=invoice.tax_total,
        shipping_total=invoice.shipping_total,
        total=invoice.total,
        total_base=invoice.total_base,
        order_id=invoice.order_id,
        tax_breakup=breakup or [],
    )


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status: str | None = None,
    customer_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_INVOICES_VIEW)),
    session: Session = Depends(get_db),
):
    stmt = select(CustomerInvoice).where(CustomerInvoice.company_id == ctx.company_id).order_by(CustomerInvoice.invoice_date.desc())
    if status:
        stmt = stmt.where(CustomerInvoice.status == status)
    if customer_id:
        stmt = stmt.where(CustomerInvoice.customer_id == customer_id)
    invoices = session.execute(stmt).scalars().all()
    breakup = _breakup_map(session, [i.id for i in invoices])
    return [_invoice_out(i, breakup.get(i.id, [])) for i in invoices]


def _invoice_detail(session: Session, invoice: CustomerInvoice) -> InvoiceOut:
    return _invoice_out(invoice, _breakup_map(session, [invoice.id]).get(invoice.id, []))


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: str, ctx: CompanyCtx = Depends(guard(P_INVOICES_VIEW)), session: Session = Depends(get_db)):
    return _invoice_detail(session, svc.get_invoice(session, ctx.company_id, invoice_id))


@router.get("/{invoice_id}/lines", response_model=list[InvoiceLineOut])
def invoice_lines(invoice_id: str, ctx: CompanyCtx = Depends(guard(P_INVOICES_VIEW)), session: Session = Depends(get_db)):
    invoice = svc.get_invoice(session, ctx.company_id, invoice_id)
    lines = svc.get_invoice_lines(session, invoice.id)
    return [
        InvoiceLineOut(
            id=l.id, product_id=l.product_id, sku_snapshot=l.sku_snapshot,
            hsn_sac=l.hsn_sac_snapshot,
            description_snapshot=l.description_snapshot, qty=l.qty, unit_price=l.unit_price,
            discount=l.discount, tax_percentage=l.tax_percentage, line_total=l.line_total,
            tax_amount=l.tax_amount,
        )
        for l in lines
    ]


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(payload: InvoiceCreateIn, ctx: CompanyCtx = Depends(guard(P_INVOICES_MANAGE)), session: Session = Depends(get_db)):
    invoice = svc.create_invoice(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        customer_id=payload.customer_id,
        invoice_date=payload.invoice_date,
        customer_address=payload.customer_address,
        currency=payload.currency,
        lines=[l.model_dump() for l in payload.lines],
        shipping_total=payload.shipping_total,
        discount=payload.discount,
        notes=payload.notes,
        due_date=payload.due_date,
        order_id=payload.order_id,
        source="order" if payload.order_id else "manual",
    )
    if payload.post:
        svc.post_invoice(session, invoice, ctx.user.id)
        log_action(session, action="invoice.posted", entity_type="customer_invoice", entity_id=invoice.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"doc_number": invoice.doc_number, "total": str(invoice.total)})
    else:
        log_action(session, action="invoice.created", entity_type="customer_invoice", entity_id=invoice.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _invoice_detail(session, invoice)


@router.post("/{invoice_id}/post", response_model=InvoiceOut)
def post_invoice(invoice_id: str, ctx: CompanyCtx = Depends(guard(P_INVOICES_MANAGE)), session: Session = Depends(get_db)):
    invoice = svc.get_invoice(session, ctx.company_id, invoice_id)
    invoice, _ = svc.post_invoice(session, invoice, ctx.user.id)
    log_action(session, action="invoice.posted", entity_type="customer_invoice", entity_id=invoice.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _invoice_detail(session, invoice)


@router.post("/{invoice_id}/reverse", response_model=InvoiceOut)
def reverse_invoice(invoice_id: str, ctx: CompanyCtx = Depends(guard(P_INVOICES_MANAGE)), session: Session = Depends(get_db)):
    invoice = svc.get_invoice(session, ctx.company_id, invoice_id)
    svc.reverse_invoice(session, invoice, ctx.user.id)
    log_action(session, action="invoice.reversed", entity_type="customer_invoice", entity_id=invoice.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return _invoice_detail(session, invoice)


class CreditNoteOut(BaseModel):
    id: str
    doc_number: str
    invoice_id: str
    customer_id: str
    status: str
    note_date: date
    total: Decimal
    reason: str | None


@router.post("/credit-notes", response_model=CreditNoteOut, status_code=201)
def create_credit_note(payload: CreditNoteIn, ctx: CompanyCtx = Depends(guard(P_INVOICES_MANAGE)), session: Session = Depends(get_db)):
    credit = svc.create_credit_note(
        session,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        invoice_id=payload.invoice_id,
        lines=[l.model_dump() for l in payload.lines],
        note_date=payload.note_date,
        reason=payload.reason,
        restock=payload.restock,
        restock_location_id=payload.restock_location_id,
    )
    log_action(session, action="credit_note.created", entity_type="credit_note", entity_id=credit.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"total": str(credit.total), "restock": payload.restock})
    return CreditNoteOut(
        id=credit.id, doc_number=credit.doc_number, invoice_id=credit.invoice_id,
        customer_id=credit.customer_id, status=credit.status, note_date=credit.note_date,
        total=credit.total, reason=credit.reason,
    )


@router.get("/credit-notes", response_model=list[CreditNoteOut])
def list_credit_notes(ctx: CompanyCtx = Depends(guard(P_INVOICES_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(select(CreditNote).where(CreditNote.company_id == ctx.company_id).order_by(CreditNote.note_date.desc())).scalars().all()
    return [
        CreditNoteOut(id=c.id, doc_number=c.doc_number, invoice_id=c.invoice_id, customer_id=c.customer_id, status=c.status, note_date=c.note_date, total=c.total, reason=c.reason)
        for c in rows
    ]


@router.get("/reports/ar-aging")
def ar_aging(
    as_of: date,
    ctx: CompanyCtx = Depends(guard("reports.view")),
    session: Session = Depends(get_db),
):
    return svc.ar_aging(session, ctx.company_id, as_of=as_of)
