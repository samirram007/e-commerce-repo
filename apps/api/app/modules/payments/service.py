"""Payments service: manual receipts/vouchers, allocations, GL posting.

Financial postings are idempotent by transaction design: allocation rows are
unique per (payment, document), and amount math validates against outstanding
balances before any journal is written.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.accounting import service as accounting
from app.modules.accounting.service import JournalLineSpec, SourceRef
from app.modules.companies.models import Company
from app.modules.companies.service import rate_for
from app.modules.payments.adapters import get_adapter
from app.modules.payments.models import PAYMENT_DIRECTIONS, PaymentAllocation, PaymentRecord
from app.shared.money import dec, money
from app.shared.numbering import allocate_number


def _company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    return company


def outstanding_for_document(session: Session, document_type: str, document_id: str) -> tuple[Decimal, str]:
    from app.modules.invoicing.models import CustomerInvoice  # late import to avoid cycles

    if document_type == "invoice":
        doc = session.get(CustomerInvoice, document_id)
        if doc is None:
            raise NotFoundError("Invoice")
        total, currency = dec(doc.total), doc.currency
    elif document_type == "vendor_bill":
        from app.modules.purchasing.models import VendorBill

        doc = session.get(VendorBill, document_id)
        if doc is None:
            raise NotFoundError("Vendor bill")
        total, currency = dec(doc.total), doc.currency
    else:
        raise BusinessRuleError("BAD_DOC_TYPE", f"Unsupported allocation target '{document_type}'")
    allocated = session.execute(
        select(func.sum(PaymentAllocation.amount)).where(
            PaymentAllocation.document_type == document_type, PaymentAllocation.document_id == document_id
        )
    ).scalar() or Decimal("0")
    return money(total - dec(allocated), 2), currency


def _get_adapter(name: str = "mock"):
    """Indirection so the service can inject a different provider in tests."""
    return get_adapter(name)


def create_manual_payment(
    session: Session, *, company_id: str, actor_user_id: str,
    direction: str, method: str = "cash",  # cash|bank
    party_type: str | None, party_id: str | None,
    amount, occurred_at: date,
    allocations: list[dict] | None = None,  # document_type, document_id, amount
    notes: str | None = None,
) -> PaymentRecord:
    """Record a manual cash/bank receipt or payment voucher with allocations.

    GL effect: money flows move the cash/bank account against AR/AP (and any
    unallocated remainder goes to a clearing account until allocated).
    """
    if direction not in PAYMENT_DIRECTIONS:
        raise BusinessRuleError("BAD_DIRECTION", f"direction must be in {PAYMENT_DIRECTIONS}")
    if method not in ("cash", "bank"):
        raise BusinessRuleError("BAD_METHOD", "method must be cash or bank")
    amount = money(dec(amount), 2)
    if amount <= 0:
        raise BusinessRuleError("BAD_AMOUNT", "amount must be > 0")
    company = _company(session, company_id)
    exchange_rate = dec(rate_for(session, company_id=company_id, from_currency=company.base_currency, base_currency=company.base_currency, on_date=occurred_at))

    doc_number = allocate_number(session, company_id, "receipt" if direction == "receipt" else "payment")
    record = PaymentRecord(
        company_id=company_id,
        direction=direction,
        method=method,
        provider="manual",
        provider_ref=doc_number,
        status="succeeded",
        amount=amount,
        currency=company.base_currency,
        exchange_rate=exchange_rate,
        amount_base=amount,
        customer_id=party_id if party_type == "customer" else None,
        vendor_id=party_id if party_type == "vendor" else None,
        occurred_at=datetime.combine(occurred_at, datetime.min.time()).replace(tzinfo=timezone.utc),
        notes=notes,
        created_by=actor_user_id,
    )
    session.add(record)
    session.flush()
    _post_journal_for_payment(session, record, company)
    if allocations:
        allocate_payment(session, record.company_id, record.id, allocations, actor_user_id)
    return record


def _post_journal_for_payment(session: Session, record: PaymentRecord, company: Company) -> None:
    codes = accounting.account_code_map(session, record.company_id)
    cash_account = codes["cash"] if record.method == "cash" else codes["bank"]
    is_receipt = record.direction == "receipt"
    party_ref = record.customer_id or record.vendor_id
    amount = dec(record.amount)
    # receipt: DR cash/bank, CR AR; payment: DR AP, CR cash/bank
    lines = [
        JournalLineSpec(
            account_code=cash_account,
            side="debit" if is_receipt else "credit",
            amount_base=amount,
            party_ref=party_ref,
            description=f"Payment {record.provider_ref}",
        ),
        JournalLineSpec(
            account_code=codes["ar"] if is_receipt else codes["ap"],
            side="credit" if is_receipt else "debit",
            amount_base=amount,
            party_ref=party_ref,
            description=f"Payment {record.provider_ref}",
        ),
    ]
    entry = accounting.post_journal_entry(
        session,
        company_id=record.company_id,
        entry_date=record.occurred_at.date(),
        source=SourceRef(type="payment", id=record.id),
        lines=lines,
        description=f"{'Receipt' if is_receipt else 'Payment'} {record.provider_ref}",
        actor_user_id=record.created_by,
        currency=record.currency,
        exchange_rate=record.exchange_rate,
        base_currency=company.base_currency,
    )
    record.journal_entry_id = entry.id
    session.flush()


def allocate_payment(
    session: Session, company_id: str, payment_id: str, allocations: list[dict], actor_user_id: str | None
) -> list[PaymentAllocation]:
    payment = session.get(PaymentRecord, payment_id)
    if payment is None or payment.company_id != company_id:
        raise NotFoundError("Payment")
    total_allocated = Decimal("0")
    created = []
    for item in allocations:
        doc_type = item.get("document_type")
        doc_id = item.get("document_id")
        amount = money(dec(item["amount"]), 2)
        existing = session.scalar(
            select(PaymentAllocation).where(
                PaymentAllocation.payment_id == payment_id, PaymentAllocation.document_id == doc_id
            )
        )
        if existing is not None:
            raise BusinessRuleError("ALREADY_ALLOCATED", "This document is already allocated to the payment")
        outstanding, _ = outstanding_for_document(session, doc_type, doc_id)
        if amount > outstanding:
            raise BusinessRuleError(
                "OVER_ALLOCATION",
                f"Allocating {amount} exceeds outstanding {outstanding} for document {doc_id}",
            )
        row = PaymentAllocation(
            company_id=company_id,
            payment_id=payment_id,
            document_type=doc_type,
            document_id=doc_id,
            amount=amount,
            allocated_at=datetime.now(timezone.utc),
        )
        session.add(row)
        created.append(row)
        total_allocated += amount
    session.flush()
    return created


# ---- (customer) gateway charges: intents, capture confirmation, refunds ----
def create_provider_intent(
    session: Session, *, company_id: str, actor_user_id: str | None, customer_id: str | None,
    order_id: str, receipt: str, amount, currency: str, method: str,
    adapter, creds, idempotency_key: str,
) -> tuple[PaymentRecord, "IntentResult"]:
    """Create a provider payment intent for an order and record it as pending.

    The browser collects the card through `intent.client_payload`; the order is
    only marked paid later, once `verify_client_payment` or a webhook confirms
    the money moved. Retries reuse the pending row for the same order+provider,
    and the provider-side Idempotency-Key returns the same intent id.
    """
    from app.modules.payments.adapters import IntentResult

    company = _company(session, company_id)
    intent: IntentResult = adapter.create_intent(
        creds,
        amount=money(dec(amount), 2),
        currency=currency,
        receipt=receipt,
        customer={"ref": customer_id} if customer_id else {},
        idempotency_key=idempotency_key,
    )
    record = session.scalar(
        select(PaymentRecord).where(
            PaymentRecord.order_id == order_id,
            PaymentRecord.provider == adapter.name,
            PaymentRecord.direction == "receipt",
            PaymentRecord.status.in_(("pending", "failed")),
        ).order_by(PaymentRecord.occurred_at.desc())
    )
    if record is None:
        exchange_rate = dec(
            rate_for(
                session, company_id=company_id, from_currency=currency,
                base_currency=company.base_currency,
                on_date=datetime.now(timezone.utc).date(),
            )
        )
        record = PaymentRecord(
            company_id=company_id,
            direction="receipt",
            method=method,
            provider=adapter.name,
            status="pending",
            amount=money(dec(amount), 2),
            currency=currency,
            exchange_rate=exchange_rate,
            amount_base=money(dec(amount) * exchange_rate, 2),
            customer_id=customer_id,
            order_id=order_id,
            occurred_at=datetime.now(timezone.utc),
            idempotency_scope="checkout",
            created_by=actor_user_id,
        )
        session.add(record)
    # A retry after a failure reuses the row (and the provider returns the same
    # intent id for the same Idempotency-Key), so (provider, provider_ref) never
    # collides and the order keeps a single payment history.
    record.status = "pending"
    record.provider_ref = intent.intent_id
    record.mode = creds.mode
    session.flush()
    return record, intent


def mark_succeeded(session: Session, record: PaymentRecord, charge_ref: str | None = None) -> PaymentRecord:
    """Flip a pending record to succeeded (webhook/client confirmation)."""
    if record.status != "succeeded":
        record.status = "succeeded"
        if charge_ref and charge_ref != record.provider_ref and record.provider != "mock":
            # Razorpay charges are refunded by payment id, not order id.
            record.charge_ref = charge_ref
        session.flush()
    return record


def mark_failed(session: Session, record: PaymentRecord, message: str | None = None) -> PaymentRecord:
    if record.status in ("pending", "failed"):
        record.status = "failed"
        if message:
            record.notes = (f"{record.notes}\n" if record.notes else "") + f"Failed: {message}"[:400]
        session.flush()
    return record


def pending_for_order(session: Session, order_id: str, provider: str | None = None) -> PaymentRecord | None:
    stmt = select(PaymentRecord).where(
        PaymentRecord.order_id == order_id,
        PaymentRecord.direction == "receipt",
        PaymentRecord.status == "pending",
    )
    if provider:
        stmt = stmt.where(PaymentRecord.provider == provider)
    return session.execute(stmt.order_by(PaymentRecord.occurred_at.desc())).scalars().first()


def provider_refund(
    session: Session, *, company_id: str, actor_user_id: str, original: PaymentRecord, amount, currency: str | None = None,
) -> PaymentRecord:
    """refund an amount back to the original charge reference.

    The refund runs against the **mode stored on the original payment**, so a
    company that has since flipped to live keys still refunds test charges with
    the test credentials they were made with.
    """
    if original.direction != "receipt" or original.status != "succeeded":
        raise BusinessRuleError("NOT_REFUNDABLE", "Only succeeded receipts can be refunded")
    amount = money(dec(amount), 2)
    if amount <= 0:
        raise BusinessRuleError("BAD_AMOUNT", "Refund amount must be > 0")
    original_refunded = session.execute(
        select(func.sum(PaymentRecord.amount)).where(
            PaymentRecord.company_id == original.company_id,
            (
                (PaymentRecord.provider_ref == f"refund_{original.provider_ref}")
                | (PaymentRecord.notes == f"Refund of {original.provider_ref}")
            ),
            PaymentRecord.status.in_(["succeeded", "pending"]),
        )
    ).scalar() or Decimal("0")
    if dec(original_refunded) + amount > dec(original.amount):
        raise BusinessRuleError("REFUND_EXCEEDS", "Refund exceeds remaining refundable amount")
    from app.modules.payments.gateways import get_gateway_by_name

    adapter, creds, _config = get_gateway_by_name(
        session, original.company_id, original.provider, mode=original.mode
    )
    result = adapter.refund(
        creds,
        provider_ref=original.charge_ref or original.provider_ref,
        amount=amount,
        currency=currency or original.currency,
        idempotency_key=f"refund:{original.provider_ref}:{amount}",
    )
    record = PaymentRecord(
        company_id=original.company_id,
        direction="receipt",
        method=original.method,
        provider=adapter.name,
        provider_ref=result.provider_ref,
        status="succeeded",
        mode=original.mode,
        amount=amount,
        currency=currency or original.currency,
        exchange_rate=original.exchange_rate,
        amount_base=money(dec(amount) * original.exchange_rate, 2),
        customer_id=original.customer_id,
        order_id=original.order_id,
        occurred_at=datetime.now(timezone.utc),
        idempotency_scope="refund",
        notes=f"Refund of {original.provider_ref}",
        created_by=actor_user_id,
    )
    session.add(record)
    session.flush()
    return record
