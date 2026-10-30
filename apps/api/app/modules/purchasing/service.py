"""Purchasing service.

Flow: draft PO -> submitted -> approved -> goods receipt (stock + PO lines
updated) -> vendor bill (AP posting). Received quantities live on PO lines and
receipt lines; stock quantities live only in the inventory module.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import new_id
from app.modules.accounting import service as accounting
from app.modules.accounting.service import JournalLineSpec, SourceRef
from app.modules.companies import service as companies_svc
from app.modules.companies.models import Company
from app.modules.inventory import service as inventory
from app.modules.partners import service as partners
from app.modules.purchasing.models import (
    PO_STATUSES,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    VendorBill,
    VendorBillLine,
)
from app.modules.storage import service as storage_svc
from app.modules.taxes import service as taxes
from app.shared.money import dec, money
from app.shared.numbering import allocate_number

ALLOWED_TRANSITIONS = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"approved", "cancelled"},
    "approved": {"partially_received", "received", "cancelled", "closed"},
    "partially_received": {"received", "closed"},
    "received": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


def get_po(session: Session, company_id: str, po_id: str) -> PurchaseOrder:
    order = session.get(PurchaseOrder, po_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Purchase order")
    return order


def get_po_lines(session: Session, order_id: str) -> list[PurchaseOrderLine]:
    return list(
        session.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.order_id == order_id).order_by(PurchaseOrderLine.line_number)).scalars()
    )


def create_po(
    session: Session, *, company_id: str, actor_user_id: str, vendor_id: str, order_date: date,
    expected_date: date | None, currency: str, notes: str | None,
    lines: list[dict],
) -> PurchaseOrder:
    partners.get_vendor(session, company_id, vendor_id)
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    base_currency = company.base_currency
    exchange_rate = dec(companies_svc.rate_for(session, company_id=company_id, from_currency=currency, base_currency=base_currency, on_date=order_date))
    if not lines:
        raise BusinessRuleError("NO_LINES", "A purchase order needs at least one line")
    doc_number = allocate_number(session, company_id, "purchase_order")
    order = PurchaseOrder(
        company_id=company_id,
        doc_number=doc_number,
        vendor_id=vendor_id,
        status="draft",
        order_date=order_date,
        expected_date=expected_date,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
        created_by=actor_user_id,
    )
    session.add(order)
    session.flush()
    for index, line in enumerate(lines, start=1):
        product = inventory.get_product_check(session, line["product_id"], company_id)
        if not product.is_purchasable:
            raise BusinessRuleError("NOT_PURCHASABLE", f"Product {product.sku} is not purchasable")
        ordered_qty = dec(line["ordered_qty"])
        unit_cost = dec(line["unit_cost"])
        if ordered_qty <= 0:
            raise BusinessRuleError("BAD_QTY", "ordered_qty must be > 0")
        if unit_cost < 0:
            raise BusinessRuleError("BAD_COST", "unit_cost must be >= 0")
        session.add(
            PurchaseOrderLine(
                order_id=order.id,
                product_id=product.id,
                uom_id=line.get("uom_id"),
                ordered_qty=money(ordered_qty, 4),
                unit_cost=money(unit_cost, 2),
                tax_rate_id=line.get("tax_rate_id"),
                line_number=index,
                notes=line.get("notes"),
            )
        )
    session.flush()
    return order


def _validate_transition(order: PurchaseOrder, to_status: str) -> None:
    if to_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise BusinessRuleError(
            "BAD_STATUS_TRANSITION", f"Cannot move a {order.status} PO to '{to_status}'"
        )


def transition_po(session: Session, company_id: str, po_id: str, to_status: str, actor_user_id: str) -> PurchaseOrder:
    order = get_po(session, company_id, po_id)
    _validate_transition(order, to_status)
    order.status = to_status
    if to_status == "approved":
        order.approved_by = actor_user_id
        order.approved_at = datetime.now(timezone.utc)
    if to_status == "closed":
        order.closed_at = datetime.now(timezone.utc)
    session.flush()
    return order


def receive_goods(
    session: Session, *, company_id: str, po_id: str, actor_user_id: str,
    lines: list[dict],
) -> GoodsReceipt:
    """Post a goods receipt against a PO. `lines`: order_line_id, qty_received,
    location_id, optional batch_ref/expiry_date."""
    order = get_po(session, company_id, po_id)
    if order.status not in ("approved", "partially_received"):
        raise BusinessRuleError("PO_NOT_RECEIVABLE", f"PO status '{order.status}' cannot receive goods")
    if not lines:
        raise BusinessRuleError("NO_LINES", "Receipt needs at least one line")

    receipt_lines_payload: list[tuple[PurchaseOrderLine, Decimal, str, str | None, object | None, list[str] | None]] = []
    for payload in lines:
        po_line = session.get(PurchaseOrderLine, payload["order_line_id"])
        if po_line is None or po_line.order_id != order.id:
            raise NotFoundError("Purchase order line")
        remaining = dec(po_line.ordered_qty) - dec(po_line.received_qty)
        qty = dec(payload["qty_received"])
        if qty <= 0:
            raise BusinessRuleError("BAD_QTY", "qty_received must be > 0")
        if qty - remaining > Decimal("0.0001"):
            raise BusinessRuleError(
                "OVER_RECEIPT",
                f"Line {po_line.line_number}: receiving {qty} exceeds remaining {remaining}",
            )
        location = storage_svc.get_location(session, company_id, payload["location_id"])
        if location.location_type not in storage_svc.STOCKABLE_TYPES:
            raise BusinessRuleError("BIN_REQUIRED", "Goods receipts must target bin-level locations")
        raw_serials = payload.get("serials") or []
        serials = [s.strip() for s in raw_serials if s and str(s).strip()] or None
        receipt_lines_payload.append(
            (po_line, qty, location.id, payload.get("batch_ref"), payload.get("expiry_date"), serials)
        )

    doc_number = allocate_number(session, company_id, "goods_receipt")
    receipt = GoodsReceipt(
        company_id=company_id,
        doc_number=doc_number,
        order_id=order.id,
        status="posted",
        received_at=datetime.now(timezone.utc),
        location_id=receipt_lines_payload[0][2],
        created_by=actor_user_id,
    )
    session.add(receipt)
    session.flush()

    all_received = True
    for po_line, qty, location_id, batch_ref, expiry, serials in receipt_lines_payload:
        grl = GoodsReceiptLine(
            receipt_id=receipt.id,
            order_line_id=po_line.id,
            product_id=po_line.product_id,
            location_id=location_id,
            qty_received=money(qty, 4),
            unit_cost=po_line.unit_cost,
            batch_ref=batch_ref,
            expiry_date=expiry,
        )
        session.add(grl)
        session.flush()
        inventory.post_movement(
            session,
            company_id=company_id,
            movement_type="receipt",
            product_id=po_line.product_id,
            location_id=location_id,
            quantity=qty,
            unit_cost=po_line.unit_cost,
            batch_ref=batch_ref,
            expiry_date=expiry,
            serials=serials,
            source_type="goods_receipt",
            source_id=receipt.id,
            source_line_id=grl.id,
            actor_user_id=actor_user_id,
        )
        po_line.received_qty = money(dec(po_line.received_qty) + qty, 4)
        if dec(po_line.received_qty) < dec(po_line.ordered_qty):
            all_received = False
        order.received_qty = money(dec(order.received_qty) + qty, 4)
    order.status = "received" if all_received else "partially_received"
    session.flush()
    return receipt


def _input_tax_lines(
    session: Session,
    company_id: str,
    codes: dict[str, str],
    tax_total: Decimal,
    tax_by_slab: list[tuple[Decimal, Decimal]],
    precision: int,
    *,
    party_ref: str | None,
) -> list[JournalLineSpec]:
    """Input tax debit split into CGST/SGST tax-credit accounts where the chart
    has them; the SGST leg takes the remainder so the entry stays balanced. Falls
    back to the single tax account on charts created before the GST split."""
    if tax_total <= 0:
        return []
    gst_codes = accounting.gst_input_codes(session, company_id, codes)
    if gst_codes is None:
        return [
            JournalLineSpec(
                account_code=codes["sales_tax_payable"],
                side="debit",
                amount_base=tax_total,
                description="Input tax",
                party_ref=party_ref,
            )
        ]
    cgst = taxes.cgst_share(tax_by_slab, precision=precision)
    return [
        JournalLineSpec(
            account_code=gst_codes[0],
            side="debit",
            amount_base=cgst,
            description="Input CGST",
            party_ref=party_ref,
        ),
        JournalLineSpec(
            account_code=gst_codes[1],
            side="debit",
            amount_base=money(tax_total - cgst, precision),
            description="Input SGST",
            party_ref=party_ref,
        ),
    ]


def create_bill_from_receipt(
    session: Session, *, company_id: str, receipt_id: str, actor_user_id: str,
    bill_date: date, vendor_ref: str | None = None, notes: str | None = None,
) -> VendorBill:
    """Create + post a vendor bill from a goods receipt (AP posting)."""
    receipt = session.get(GoodsReceipt, receipt_id)
    if receipt is None or receipt.company_id != company_id:
        raise NotFoundError("Goods receipt")
    if receipt.status != "posted":
        raise BusinessRuleError("RECEIPT_NOT_POSTED", "Only posted receipts can be billed")
    if session.scalar(select(VendorBill.id).where(VendorBill.receipt_id == receipt.id, VendorBill.status == "posted")):
        raise BusinessRuleError("ALREADY_BILLED", "This receipt already has a posted bill")
    order = get_po(session, company_id, receipt.order_id)
    vendor = partners.get_vendor(session, company_id, order.vendor_id)
    company = session.get(Company, company_id)
    base_currency = company.base_currency
    currency = order.currency
    exchange_rate = dec(companies_svc.rate_for(session, company_id=company_id, from_currency=currency, base_currency=base_currency, on_date=bill_date))

    gr_lines = session.execute(select(GoodsReceiptLine).where(GoodsReceiptLine.receipt_id == receipt.id)).scalars().all()
    if not gr_lines:
        raise BusinessRuleError("EMPTY_RECEIPT", "Receipt has no lines to bill")

    inventory_value = Decimal("0")
    tax_total = Decimal("0")
    tax_by_slab: list[tuple[Decimal, Decimal]] = []
    precision = 2
    doc_number = allocate_number(session, company_id, "vendor_bill")
    bill = VendorBill(
        company_id=company_id,
        doc_number=doc_number,
        vendor_ref=vendor_ref,
        order_id=order.id,
        receipt_id=receipt.id,
        vendor_id=vendor.id,
        status="posted",
        bill_date=bill_date,
        due_date=bill_date + timedelta(days=int(vendor.payment_term_days or 0)),
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
        created_by=actor_user_id,
    )
    session.add(bill)
    session.flush()

    for gr_line in gr_lines:
        po_line = session.get(PurchaseOrderLine, gr_line.order_line_id)
        line_total = money(dec(gr_line.qty_received) * dec(gr_line.unit_cost), precision)
        percentage = (
            dec(taxes.get_tax_rate(session, company_id, po_line.tax_rate_id).percentage)
            if po_line and po_line.tax_rate_id
            else Decimal("0")
        )
        tax_amount = money(dec(line_total) * percentage / Decimal("100"), precision)
        session.add(
            VendorBillLine(
                bill_id=bill.id,
                product_id=gr_line.product_id,
                receipt_line_id=gr_line.id,
                qty=gr_line.qty_received,
                unit_cost=gr_line.unit_cost,
                line_total=line_total,
                tax_amount=tax_amount,
                description=None,
            )
        )
        inventory_value += line_total
        tax_total += tax_amount
        tax_by_slab.append((percentage, tax_amount))

    inventory_value = money(inventory_value, precision)
    tax_total = money(tax_total, precision)
    ap_total = money(inventory_value + tax_total, precision)

    codes = accounting.account_code_map(session, company_id)
    entry = accounting.post_journal_entry(
        session,
        company_id=company_id,
        entry_date=bill_date,
        source=SourceRef(type="vendor_bill", id=bill.id),
        lines=[
            JournalLineSpec(
                account_code=codes["inventory"],
                side="debit",
                amount_base=inventory_value,
                description=f"Goods received PO {order.doc_number}",
            ),
            *_input_tax_lines(
                session, company_id, codes, tax_total, tax_by_slab, precision,
                party_ref=vendor.id,
            ),
            JournalLineSpec(
                account_code=codes["ap"],
                side="credit",
                amount_base=ap_total,
                description=f"Vendor bill {doc_number}",
                party_ref=vendor.id,
            ),
        ],
        description=f"Vendor bill {doc_number} from receipt {receipt.doc_number}",
        actor_user_id=actor_user_id,
        currency=currency,
        exchange_rate=exchange_rate,
        base_currency=base_currency,
    )
    bill.total = ap_total
    bill.total_base = money(ap_total, precision)
    bill.journal_entry_id = entry.id
    session.flush()
    return bill


def create_bill_adhoc(
    session: Session, *, company_id: str, vendor_id: str, actor_user_id: str,
    bill_date: date, lines: list[dict], currency: str = "INR",
) -> VendorBill:
    """Direct vendor bill (expense purchase without goods receipt).
    lines: product_id (optional for services), description, qty, unit_cost, tax_rate_id"""
    vendor = partners.get_vendor(session, company_id, vendor_id)
    company = session.get(Company, company_id)
    base_currency = company.base_currency
    if not lines:
        raise BusinessRuleError("NO_LINES", "Bill needs at least one line")
    exchange_rate = dec(companies_svc.rate_for(session, company_id=company_id, from_currency=currency, base_currency=base_currency, on_date=bill_date))
    doc_number = allocate_number(session, company_id, "vendor_bill")
    bill = VendorBill(
        company_id=company_id, doc_number=doc_number, vendor_id=vendor.id, status="posted",
        bill_date=bill_date, currency=currency, exchange_rate=exchange_rate, created_by=actor_user_id,
    )
    session.add(bill)
    session.flush()
    codes = accounting.account_code_map(session, company_id)
    specs: list[JournalLineSpec] = []
    total = Decimal("0")
    tax_total = Decimal("0")
    tax_by_slab: list[tuple[Decimal, Decimal]] = []
    for index, line in enumerate(lines, start=1):
        qty = dec(line["qty"])
        unit_cost = dec(line["unit_cost"])
        line_total = money(qty * unit_cost, 2)
        percentage = dec(line.get("tax_percentage", 0))
        tax = money(line_total * percentage / Decimal("100"), 2)
        product_id = line.get("product_id")
        session.add(
            VendorBillLine(
                bill_id=bill.id,
                product_id=product_id or "",
                qty=money(qty, 4),
                unit_cost=money(unit_cost, 2),
                line_total=line_total,
                tax_amount=tax,
                description=line.get("description"),
            )
        )
        specs.append(
            JournalLineSpec(
                account_code=line.get("expense_account_code") or codes["operating_expenses"],
                side="debit",
                amount_base=line_total,
                party_ref=vendor.id,
                description=line.get("description"),
            )
        )
        tax_total += tax
        tax_by_slab.append((percentage, tax))
        total += line_total + tax
    specs.extend(
        _input_tax_lines(
            session, company_id, codes, money(tax_total, 2), tax_by_slab, 2,
            party_ref=vendor.id,
        )
    )
    specs.append(
        JournalLineSpec(
            account_code=codes["ap"], side="credit", amount_base=money(total, 2),
            party_ref=vendor.id, description=f"Vendor bill {doc_number}",
        )
    )
    entry = accounting.post_journal_entry(
        session,
        company_id=company_id,
        entry_date=bill_date,
        source=SourceRef(type="vendor_bill", id=bill.id),
        lines=specs,
        description=f"Vendor bill {doc_number}",
        actor_user_id=actor_user_id,
        currency=currency,
        exchange_rate=exchange_rate,
        base_currency=base_currency,
    )
    bill.total = money(total, 2)
    bill.total_base = money(total, 2)
    bill.journal_entry_id = entry.id
    session.flush()
    return bill


def ap_aging(session: Session, company_id: str, *, as_of: date) -> dict:
    """Open AP per vendor = posted bills total minus allocated payments."""
    from app.modules.payments.models import PaymentAllocation

    bills = session.execute(
        select(VendorBill).where(VendorBill.company_id == company_id, VendorBill.status == "posted").order_by(VendorBill.bill_date)
    ).scalars().all()
    out: dict[str, dict[str, Decimal]] = {}
    for bill in bills:
        paid = session.execute(
            select(func.sum(PaymentAllocation.amount)).where(
                PaymentAllocation.document_type == "vendor_bill",
                PaymentAllocation.document_id == bill.id,
            )
        ).scalar() or Decimal("0")
        outstanding = dec(bill.total) - dec(paid)
        if outstanding > 0:
            bucket = vendor_age_bucket(bill.bill_date, as_of)
            entry = out.setdefault(bill.vendor_id, {"current": Decimal("0"), "d30": Decimal("0"), "d60": Decimal("0"), "d90": Decimal("0"), "older": Decimal("0")})
            entry[bucket] += outstanding
    return {vendor_id: {bucket: str(val) for bucket, val in buckets.items()} for vendor_id, buckets in out.items()}


def vendor_age_bucket(bill_date: date, as_of: date) -> str:
    days = (as_of - bill_date).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "d30"
    if days <= 60:
        return "d60"
    if days <= 90:
        return "d90"
    return "older"
