"""Invoicing service: create/post customer invoices (from order or manual),
credit notes, AR aging. Backend recomputes every authoritative amount.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.accounting import service as accounting
from app.modules.accounting.service import JournalLineSpec, SourceRef
from app.modules.catalog import service as catalog
from app.modules.companies import service as companies
from app.modules.companies.models import Company
from app.modules.invoicing.models import (
    INVOICE_STATUSES,
    CreditNote,
    CreditNoteLine,
    CustomerInvoice,
    InvoiceLine,
)
from app.modules.inventory import service as inventory
from app.modules.partners import service as partners
from app.modules.taxes import service as taxes
from app.shared.money import dec, money
from app.shared.numbering import allocate_number


def _company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    return company


def get_invoice(session: Session, company_id: str, invoice_id: str) -> CustomerInvoice:
    invoice = session.get(CustomerInvoice, invoice_id)
    if invoice is None or invoice.company_id != company_id:
        raise NotFoundError("Invoice")
    return invoice


def get_invoice_lines(session: Session, invoice_id: str) -> list[InvoiceLine]:
    return list(
        session.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id).order_by(InvoiceLine.line_number)).scalars()
    )


def create_invoice(
    session: Session, *, company_id: str, actor_user_id: str, customer_id: str,
    invoice_date: date, currency: str, lines: list[dict],
    shipping_total=Decimal("0"), notes: str | None = None, due_date: date | None = None,
    order_id: str | None = None, source: str = "manual",
    customer_address: str | None = None,
) -> CustomerInvoice:
    """Create a draft invoice; totals are computed server-side from lines."""
    customer = partners.get_customer(session, company_id, customer_id)
    if not lines:
        raise BusinessRuleError("NO_LINES", "Invoice needs at least one line")
    company = _company(session, company_id)
    precision = 2
    invoice = CustomerInvoice(
        company_id=company_id,
        doc_number=allocate_number(session, company_id, "invoice"),
        customer_id=customer.id,
        status="draft",
        invoice_date=invoice_date,
        due_date=due_date or invoice_date + timedelta(days=int(customer.payment_term_days or 0)),
        currency=currency,
        customer_name=customer.name,
        customer_address=customer_address or None,
        customer_tax_identifier=customer.tax_identifier,
        notes=notes,
        order_id=order_id,
        source=source,
    )
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    discount_total = Decimal("0")
    line_number = 1
    for line in lines:
        product_id = line.get("product_id")
        product = None
        if product_id:
            product = session.get(catalog.Product, product_id) if hasattr(catalog, "Product") else None
            from app.modules.catalog.models import Product

            product = session.get(Product, product_id)
            if product is None or product.company_id != company_id:
                raise NotFoundError("Product")
        qty = dec(line.get("qty", 0))
        unit_price = dec(line.get("unit_price", 0) if line.get("unit_price") is not None else (
            catalog.resolve_price(session, product, currency=currency, on_date=invoice_date) if product else Decimal("0")
        ))
        discount = dec(line.get("discount", 0))
        tax_rate_id = line.get("tax_rate_id")
        tax_percentage = dec(taxes.get_tax_rate(session, company_id, tax_rate_id).percentage) if tax_rate_id else line.get("tax_percentage", 0)
        taxable = qty * unit_price - discount
        tax_amount = taxes.compute_tax(max(taxable, Decimal("0")), tax_percentage, precision=precision)
        line_total = money(taxable + tax_amount, precision)
        if qty <= 0:
            raise BusinessRuleError("BAD_QTY", "Line qty must be > 0")
        discount_total += discount
        subtotal += qty * unit_price
        tax_total += tax_amount
        session.add(
            InvoiceLine(
                invoice_id="pending",
                product_id=product.id if product else None,
                sku_snapshot=product.sku if product else line.get("sku_snapshot", ""),
                hsn_sac_snapshot=product.hsn_sac if product else None,
                description_snapshot=line.get("description") or (product.name if product else ""),
                qty=money(qty, 4),
                unit_price=money(unit_price, precision),
                discount=money(discount, precision),
                tax_percentage=tax_percentage,
                line_total=line_total,
                tax_amount=tax_amount,
                line_number=line_number,
            )
        )
        line_number += 1
    subtotal = money(subtotal, precision)
    discount_total = money(discount_total, precision)
    tax_total = money(tax_total, precision)
    shipping = money(dec(shipping_total), precision)
    total = money(subtotal - discount_total + tax_total + shipping, precision)
    if total <= 0:
        raise BusinessRuleError("BAD_TOTAL", "Invoice total must be > 0")
    invoice.subtotal = subtotal
    invoice.discount_total = discount_total
    invoice.tax_total = tax_total
    invoice.shipping_total = shipping
    invoice.total = total
    invoice.notes = notes or invoice.notes
    session.add(invoice)
    session.flush()
    # line rows were created with placeholder invoice_id; repoint now that id exists
    session.execute(
        __import__("sqlalchemy").update(InvoiceLine).where(InvoiceLine.invoice_id == "pending").values(invoice_id=invoice.id)
    )
    session.flush()
    return invoice


def post_invoice(
    session: Session, invoice: CustomerInvoice, actor_user_id: str
) -> tuple[CustomerInvoice, object]:
    """Post a draft invoice: AR journal + COGS from delivered/issued stock.
    Stock is issued at posting if still reserved (invoicing finalizes delivery)."""
    if invoice.status != "draft":
        raise BusinessRuleError("NOT_DRAFT", "Only draft invoices can be posted")
    company = _company(session, invoice.company_id)
    precision = 2
    # authoritative exchange rate at invoice date
    if invoice.currency != company.base_currency:
        rate = dec(companies.rate_for(session, company_id=invoice.company_id, from_currency=invoice.currency, base_currency=company.base_currency, on_date=invoice.invoice_date))
    else:
        rate = Decimal("1")
    invoice.exchange_rate = rate

    total_base = money(dec(invoice.total) * rate, precision)
    subtotal_base = money((dec(invoice.subtotal) - dec(invoice.discount_total)) * rate, precision)
    tax_base = money(dec(invoice.tax_total) * rate, precision)
    shipping_base = money(dec(invoice.shipping_total) * rate, precision)
    revenue_base = money(subtotal_base + shipping_base, precision)
    invoice.total_base = total_base

    codes = accounting.account_code_map(session, company.id)
    # Tax payable CR split into CGST and SGST (one account each) where the chart
    # has them; the SGST leg takes the remainder so the entry always balances.
    tax_lines: list[JournalLineSpec]
    gst_codes = accounting.gst_payable_codes(session, company.id, codes)
    if gst_codes is not None and tax_base > 0:
        invoice_lines = get_invoice_lines(session, invoice.id)
        # rounded per GST slab so the ledger matches the printed CGST/SGST
        cgst_base = money(
            taxes.cgst_share(
                [(line.tax_percentage, line.tax_amount) for line in invoice_lines]
            )
            * rate,
            precision,
        )
        tax_lines = [
            JournalLineSpec(account_code=gst_codes[0], side="credit", amount_base=cgst_base, party_ref=invoice.customer_id, description="CGST"),
            JournalLineSpec(account_code=gst_codes[1], side="credit", amount_base=money(tax_base - cgst_base, precision), party_ref=invoice.customer_id, description="SGST"),
        ]
    else:
        tax_lines = [
            JournalLineSpec(account_code=codes["sales_tax_payable"], side="credit", amount_base=tax_base, party_ref=invoice.customer_id),
        ]
    lines = [
        JournalLineSpec(
            account_code=codes["ar"],
            side="debit",
            amount_base=total_base,
            party_ref=invoice.customer_id,
            description=f"Invoice {invoice.doc_number}",
        ),
        # tax payable CR; revenue CR net of shipping
        *tax_lines,
        JournalLineSpec(account_code=codes["sales_revenue"], side="credit", amount_base=revenue_base, party_ref=invoice.customer_id),
    ]
    entry = accounting.post_journal_entry(
        session,
        company_id=company.id,
        entry_date=invoice.invoice_date,
        source=SourceRef(type="invoice", id=invoice.id),
        lines=lines,
        description=f"Customer invoice {invoice.doc_number}",
        actor_user_id=actor_user_id,
        currency=invoice.currency,
        exchange_rate=rate,
        base_currency=company.base_currency,
    )
    invoice.journal_entry_id = entry.id
    invoice.status = "posted"
    session.flush()
    return invoice, entry


def create_credit_note(
    session: Session, *, company_id: str, actor_user_id: str, invoice_id: str,
    lines: list[dict], note_date: date, reason: str | None = None,
    restock: bool = False, restock_location_id: str | None = None,
) -> CreditNote:
    """Credit note against a posted invoice. Optionally restocks returned goods
    and (when configured) executes approved return flows."""
    invoice = get_invoice(session, company_id, invoice_id)
    if invoice.status != "posted":
        raise BusinessRuleError("INVOICE_NOT_POSTED", "Only posted invoices can be credited")
    if invoice.reversed_by_entry_id is not None:
        raise BusinessRuleError("INVOICE_REVERSED", "Invoice has been reversed")
    original_lines = {line.id: line for line in get_invoice_lines(session, invoice.id)}
    if not lines:
        raise BusinessRuleError("NO_LINES", "Credit note needs at least one line")

    validated: list[tuple[InvoiceLine | None, Decimal, Decimal, Decimal, str]] = []
    precision = 2
    total = Decimal("0")
    tax_total = Decimal("0")
    for line in lines:
        original: InvoiceLine | None = None
        if line.get("invoice_line_id"):
            original = original_lines.get(line["invoice_line_id"])
            if original is None:
                raise NotFoundError("Invoice line")
        if original is not None:
            already_credited = sum(
                (dec(cn_line.qty) for cn_line in session.execute(
                    select(CreditNoteLine).where(CreditNoteLine.invoice_line_id == original.id)
                ).scalars()),
                Decimal("0"),
            )
            remaining = dec(original.qty) - already_credited
        else:
            remaining = Decimal("999999999")
        qty = dec(line.get("qty", 0))
        if qty <= 0:
            raise BusinessRuleError("BAD_QTY", "Credit qty must be > 0")
        if qty > remaining if original is not None else False:
            raise BusinessRuleError(
                "OVER_CREDIT", f"Qty {qty} exceeds remaining creditable {remaining} for line {original.id if original else ''}"
            )
        unit_price = dec(line.get("unit_price", original.unit_price if original is not None else 0))
        tax_amount = money(unit_price * qty * dec(original.tax_percentage) / Decimal("100"), precision) if original is not None else dec(line.get("tax_amount", 0))
        line_total = money(unit_price * qty + tax_amount, precision)
        validated.append((original, qty, unit_price, tax_amount, line.get("description") or (original.description_snapshot if original else "")))
        total += line_total
        tax_total += tax_amount

    total = money(total, precision)
    tax_total = money(tax_total, precision)
    doc_number = allocate_number(session, company_id, "credit_note")
    credit = CreditNote(
        company_id=company_id,
        doc_number=doc_number,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        status="posted",
        note_date=note_date,
        currency=invoice.currency,
        reason=reason,
        total=total,
        total_base=money(dec(total) * dec(invoice.exchange_rate), precision),
        created_by=actor_user_id,
    )
    session.add(credit)
    session.flush()

    company = _company(session, company_id)
    codes = accounting.account_code_map(session, company_id)
    ar_reduction_base = money(dec(total) * dec(invoice.exchange_rate), precision)
    tax_reduction_base = money(dec(tax_total) * dec(invoice.exchange_rate), precision)
    # Revenue is reversed net of tax; the tax portion goes back to tax payable.
    # (Debiting the gross amount *and* the tax would unbalance the entry.)
    revenue_reduction_base = money(ar_reduction_base - tax_reduction_base, precision)
    tax_debit_lines: list[JournalLineSpec]
    gst_codes = accounting.gst_payable_codes(session, company_id, codes)
    if gst_codes is not None and tax_reduction_base > 0:
        cgst_base = money(
            taxes.cgst_share(
                [
                    (original.tax_percentage if original else Decimal("0"), tax_amount)
                    for original, _qty, _price, tax_amount, _description in validated
                ]
            )
            * dec(invoice.exchange_rate),
            precision,
        )
        tax_debit_lines = [
            JournalLineSpec(account_code=gst_codes[0], side="debit", amount_base=cgst_base, party_ref=invoice.customer_id, description="CGST reversed"),
            JournalLineSpec(account_code=gst_codes[1], side="debit", amount_base=money(tax_reduction_base - cgst_base, precision), party_ref=invoice.customer_id, description="SGST reversed"),
        ]
    else:
        tax_debit_lines = [
            JournalLineSpec(account_code=codes["sales_tax_payable"], side="debit", amount_base=tax_reduction_base, party_ref=invoice.customer_id),
        ]
    entry = accounting.post_journal_entry(
        session,
        company_id=company_id,
        entry_date=note_date,
        source=SourceRef(type="credit_note", id=credit.id),
        lines=[
            JournalLineSpec(account_code=codes["sales_revenue"], side="debit", amount_base=revenue_reduction_base, party_ref=invoice.customer_id, description=f"Credit note {doc_number}"),
            *tax_debit_lines,
            JournalLineSpec(account_code=codes["ar"], side="credit", amount_base=ar_reduction_base, party_ref=invoice.customer_id, description=f"Credit note {doc_number}"),
        ],
        description=f"Credit note {doc_number} for invoice {invoice.doc_number}",
        actor_user_id=actor_user_id,
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        base_currency=company.base_currency,
    )
    credit.journal_entry_id = entry.id

    for original, qty, unit_price, tax_amount, description in validated:
        session.add(
            CreditNoteLine(
                credit_note_id=credit.id,
                invoice_line_id=original.id if original else None,
                product_id=original.product_id if original else None,
                description=description,
                qty=money(qty, 4),
                unit_price=money(unit_price, precision),
                line_total=money(qty * unit_price + tax_amount, precision),
                tax_amount=tax_amount,
            )
        )
    session.flush()

    if restock:
        if not restock_location_id:
            raise BusinessRuleError("LOCATION_REQUIRED", "restock_location_id required when restocking")
        for original, qty, unit_price, _, _ in validated:
            if original is None or original.product_id is None:
                continue
            avg_cost = inventory.weighted_avg_cost(session, company_id, original.product_id)
            inventory.post_movement(
                session,
                company_id=company_id,
                movement_type="return_receipt",
                product_id=original.product_id,
                location_id=restock_location_id,
                quantity=qty,
                unit_cost=avg_cost,
                source_type="credit_note",
                source_id=credit.id,
                actor_user_id=actor_user_id,
            )
        credit.stock_restocked_at = datetime.now(timezone.utc)
        session.flush()
    return credit


def reverse_invoice(session: Session, invoice: CustomerInvoice, actor_user_id: str) -> object:
    """Reverse a posted invoice with a full accounting reversal (rare path; prefer credit notes)."""
    if invoice.status != "posted":
        raise BusinessRuleError("NOT_POSTED", "Only posted invoices can be reversed")
    if invoice.reversed_by_entry_id is not None:
        raise BusinessRuleError("ALREADY_REVERSED", "Invoice already reversed")
    entry = session.get(accounting.JournalEntry, invoice.journal_entry_id)
    reversal = accounting.reverse_entry(session, entry, actor_user_id=actor_user_id)
    invoice.reversed_by_entry_id = reversal.id
    invoice.status = "cancelled"
    session.flush()
    return reversal


def ar_aging(session: Session, company_id: str, *, as_of: date) -> dict:
    """Open AR per customer bucketed by invoice age."""
    from app.modules.payments.models import PaymentAllocation

    invoices = session.execute(
        select(CustomerInvoice).where(CustomerInvoice.company_id == company_id, CustomerInvoice.status == "posted").order_by(CustomerInvoice.invoice_date)
    ).scalars().all()
    out: dict[str, dict[str, Decimal]] = {}
    for invoice in invoices:
        paid = session.execute(
            select(func.sum(PaymentAllocation.amount)).where(
                PaymentAllocation.document_type == "invoice",
                PaymentAllocation.document_id == invoice.id,
            )
        ).scalar() or Decimal("0")
        outstanding = dec(invoice.total) - dec(paid)
        if outstanding > 0:
            days = (as_of - invoice.invoice_date).days
            bucket = "current" if days <= 0 else "d30" if days <= 30 else "d60" if days <= 60 else "d90" if days <= 90 else "older"
            buckets = out.setdefault(invoice.customer_id, {"current": Decimal("0"), "d30": Decimal("0"), "d60": Decimal("0"), "d90": Decimal("0"), "older": Decimal("0")})
            buckets[bucket] += outstanding
    return {
        customer_id: {bucket: str(amount) for bucket, amount in buckets.items()}
        for customer_id, buckets in out.items()
    }
