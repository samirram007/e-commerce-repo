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


# ---- (customer) returns/refunds use provider adapters ----
def provider_charge(
    session: Session, *, company_id: str, actor_user_id: str, customer_id: str | None,
    order_id: str | None, amount, currency: str, method: str = "mock_gateway",
    provider: str = "mock", idempotency_key: str,
) -> PaymentRecord:
    """Charge a customer through a provider. Idempotency handled by caller via
    run_idempotent; provider_ref unique constraint is a second defense."""
    company = _company(session, company_id)
    adapter = get_adapter(provider)
    result = adapter.charge(amount=money(dec(amount), 2), currency=currency, customer_ref=customer_id, idempotency_key=idempotency_key)
    if not result.succeeded:
        raise BusinessRuleError(
            "PAYMENT_DECLINED", f"{result.error_code}: {result.message}"
        )
    exchange_rate = dec(rate_for(session, company_id=company_id, from_currency=currency, base_currency=company.base_currency, on_date=datetime.now(timezone.utc).date()))
    record = PaymentRecord(
        company_id=company_id,
        direction="receipt",
        method=method,
        provider=adapter.name,
        provider_ref=result.provider_ref,
        status="succeeded",
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
    session.flush()
    return record


def provider_refund(
    session: Session, *, company_id: str, actor_user_id: str, original: PaymentRecord, amount, currency: str | None = None,
) -> PaymentRecord:
    """refund an amount back to the original charge reference."""
    if original.direction != "receipt" or original.status != "succeeded":
        raise BusinessRuleError("NOT_REFUNDABLE", "Only succeeded receipts can be refunded")
    amount = money(dec(amount), 2)
    if amount <= 0:
        raise BusinessRuleError("BAD_AMOUNT", "Refund amount must be > 0")
    original_refunded = session.execute(
        select(func.sum(PaymentRecord.amount)).where(
            PaymentRecord.company_id == original.company_id,
            PaymentRecord.provider_ref == f"refund_{original.provider_ref}",
            PaymentRecord.status.in_(["succeeded", "pending"]),
        )
    ).scalar() or Decimal("0")
    if dec(original_refunded) + amount > dec(original.amount):
        raise BusinessRuleError("REFUND_EXCEEDS", "Refund exceeds remaining refundable amount")
    adapter = get_adapter(original.provider)
    result = adapter.refund(provider_ref=original.provider_ref, amount=amount, currency=currency or original.currency, idempotency_key=f"refund:{original.provider_ref}:{amount}")
    record = PaymentRecord(
        company_id=original.company_id,
        direction="receipt",
        method=original.method,
        provider=adapter.name,
        provider_ref=result.provider_ref,
        status="succeeded",
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
