"""Returns service.

Sales return flow: requested -> approved -> completed. Completion creates the
credit note (accounting reversal), restocks resalable goods, writes off/quarantines
damaged stock, and executes the refund through the payments provider adapter.
Idempotent refund execution: the refund payment row is created inside the same
transaction as the completion; replaying completion of an already-completed
return is rejected by status validation.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.inventory import service as inventory
from app.modules.invoicing import service as invoicing
from app.modules.invoicing.models import CustomerInvoice
from app.modules.payments import service as payments
from app.modules.payments.models import PaymentRecord
from app.modules.returns.models import (
    DISPOSITIONS,
    RETURN_STATUSES,
    SalesReturn,
    SalesReturnLine,
)
from app.shared.money import dec, money
from app.shared.numbering import allocate_number


def get_return(session: Session, company_id: str, return_id: str) -> SalesReturn:
    row = session.get(SalesReturn, return_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Sales return")
    return row


def return_lines(session: Session, return_id: str) -> list[SalesReturnLine]:
    return list(session.execute(select(SalesReturnLine).where(SalesReturnLine.return_id == return_id)).scalars())


def create_sales_return(
    session: Session, *, company_id: str, actor_user_id: str | None, order_id: str,
    lines: list[dict], notes: str | None = None,
) -> SalesReturn:
    """Request a return. Quantities are validated against the order and prior
    returns by the completion step; requests may be raised per line upfront."""
    from app.modules.sales import service as sales
    from app.modules.sales.models import OrderLine

    order = sales.get_order(session, company_id, order_id)
    doc_number = allocate_number(session, company_id, "sales_return")
    return_row = SalesReturn(
        company_id=company_id,
        doc_number=doc_number,
        order_id=order.id,
        invoice_id=order.invoice_id,
        customer_id=order.customer_id,
        status="requested",
        requested_at=datetime.now(timezone.utc),
        notes=notes,
        created_by=actor_user_id,
    )
    session.add(return_row)
    session.flush()
    order_lines = {line.id: line for line in sales.get_order_lines(session, order.id)}
    for payload in lines:
        order_line = order_lines.get(payload.get("order_line_id"))
        if order_line is None:
            raise NotFoundError("Order line")
        qty = dec(payload.get("qty", 0))
        if qty <= 0:
            raise BusinessRuleError("BAD_QTY", "Return qty must be > 0")
        disposition = payload.get("disposition", "resalable")
        if disposition not in DISPOSITIONS:
            raise BusinessRuleError("BAD_DISPOSITION", f"disposition must be one of {DISPOSITIONS}")
        session.add(
            SalesReturnLine(
                return_id=return_row.id,
                order_line_id=order_line.id,
                product_id=order_line.product_id,
                qty=money(qty, 4),
                unit_price=order_line.unit_price,
                disposition=disposition,
                restock_location_id=payload.get("restock_location_id"),
            )
        )
    session.flush()
    return return_row


def approve_return(session: Session, return_row: SalesReturn, actor_user_id: str | None) -> SalesReturn:
    if return_row.status != "requested":
        raise BusinessRuleError("BAD_STATUS", f"Return status '{return_row.status}' cannot be approved")
    return_row.status = "approved"
    return_row.decided_by = actor_user_id
    return_row.decided_at = datetime.now(timezone.utc)
    session.flush()
    return return_row


def reject_return(session: Session, return_row: SalesReturn, actor_user_id: str | None) -> SalesReturn:
    if return_row.status != "requested":
        raise BusinessRuleError("BAD_STATUS", f"Return status '{return_row.status}' cannot be rejected")
    return_row.status = "rejected"
    return_row.decided_by = actor_user_id
    return_row.decided_at = datetime.now(timezone.utc)
    session.flush()
    return return_row


def cancel_order_with_refund(
    session: Session, *, company_id: str, order_id: str, actor_user_id: str | None,
    reason: str | None = None, cancel_reason: str | None = None,
) -> dict:
    """Cancel an order.

    Unpaid → release stock reservations. Paid but not shipped → reverse the
    revenue with a credit note, refund the captured amount through the original
    provider (Razorpay or mock) and release the reservations. Shipped/delivered
    orders cannot be cancelled; use a return instead.
    """
    from app.modules.sales import service as sales

    order = sales.get_order(session, company_id, order_id)
    if order.status == "cancelled":
        raise BusinessRuleError("ALREADY_CANCELLED", "Order is already cancelled")
    if order.status in ("shipped", "delivered"):
        raise BusinessRuleError(
            "ALREADY_SHIPPED", "A shipped or delivered order must go through returns"
        )

    if order.payment_state != "paid":
        sales.cancel_order(session, order, actor_user_id, cancel_reason=cancel_reason)
        return {"status": order.status, "payment_state": order.payment_state, "refund_payment_id": None, "credit_note_id": None}

    invoice = session.get(CustomerInvoice, order.invoice_id) if order.invoice_id else None
    if invoice is None or invoice.status != "posted":
        raise BusinessRuleError("NO_INVOICE", "A paid order needs its posted invoice to be refunded")
    invoice_lines = invoicing.get_invoice_lines(session, invoice.id)
    credit_note = invoicing.create_credit_note(
        session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        invoice_id=invoice.id,
        lines=[
            {
                "invoice_line_id": line.id,
                "qty": dec(line.qty),
                "description": f"Cancellation {order.doc_number}",
            }
            for line in invoice_lines
        ],
        note_date=datetime.now(timezone.utc).date(),
        reason=reason or f"Order {order.doc_number} cancelled",
    )

    original = session.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.direction == "receipt",
            PaymentRecord.status == "succeeded",
        )
        .order_by(PaymentRecord.occurred_at.desc())
    )
    refund = None
    if original is not None:
        refund = payments.provider_refund(
            session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            original=original,
            amount=dec(order.total),
        )
        refund.direction = "payment"
        refund.notes = f"Refund of {original.provider_ref}"
        session.flush()

    for line in sales.get_order_lines(session, order.id):
        if line.reserved_location_id is not None:
            inventory.release_reservation(
                session,
                company_id=order.company_id,
                product_id=line.product_id,
                quantity=line.qty,
                source_type="sales_order_cancel",
                source_id=order.id,
                actor_user_id=actor_user_id,
            )
            line.reserved_location_id = None

    order.status = "cancelled"
    order.payment_state = "refunded"
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancel_reason = cancel_reason
    session.flush()
    return {
        "status": order.status,
        "payment_state": order.payment_state,
        "refund_payment_id": refund.id if refund else None,
        "credit_note_id": credit_note.id,
    }


def request_order_return(
    session: Session, *, company_id: str, order_id: str, actor_user_id: str | None,
    lines: list[dict], notes: str | None = None,
) -> SalesReturn:
    """Shopper-facing return request against a delivered, paid order.

    `lines` carry `product_id` + `qty` (the storefront does not know internal
    order-line ids); each is mapped onto the order line for that product.
    """
    from app.modules.sales import service as sales

    order = sales.get_order(session, company_id, order_id)
    if order.payment_state != "paid":
        raise BusinessRuleError("NOT_PAID", "Only paid orders can be returned")
    if order.status != "delivered":
        raise BusinessRuleError(
            "NOT_DELIVERED", "Returns can be requested once the order is delivered"
        )
    from app.modules.catalog.models import Product

    order_lines = {line.product_id: line for line in sales.get_order_lines(session, order.id)}
    default_location = _default_restock_location(session, company_id)
    mapped: list[dict] = []
    for item in lines:
        order_line = order_lines.get(item.get("product_id"))
        if order_line is None:
            raise NotFoundError("Order line")
        qty = dec(item.get("qty", 0))
        if qty <= 0:
            raise BusinessRuleError("BAD_QTY", "Return quantity must be > 0")
        if qty > dec(order_line.qty):
            raise BusinessRuleError(
                "OVER_RETURN", f"Return quantity exceeds the ordered quantity for {order_line.sku_snapshot}"
            )
        product = session.get(Product, order_line.product_id)
        # Services have no stock to put back; they are credited and refunded.
        stockable = product is None or product.stock_type == "stock"
        mapped.append(
            {
                "order_line_id": order_line.id,
                "qty": qty,
                "disposition": "resalable" if stockable else "quarantined",
                "restock_location_id": (
                    order_line.reserved_location_id or default_location
                ) if stockable else None,
            }
        )
    if not mapped:
        raise BusinessRuleError("NO_LINES", "Choose at least one item to return")
    return create_sales_return(
        session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        order_id=order.id,
        lines=mapped,
        notes=notes,
    )


def _default_restock_location(session: Session, company_id: str) -> str | None:
    """First bin in the company — what a shopper return goes back to by default."""
    from app.modules.storage import service as storage

    for location in storage.list_locations(session, company_id):
        if location.location_type == "bin":
            return location.id
    return None


def complete_return(
    session: Session, return_row: SalesReturn, *, actor_user_id: str | None, now: datetime | None = None
) -> SalesReturn:
    """Validate quantities, create credit note, handle stock disposition, refund."""
    if return_row.status != "approved":
        raise BusinessRuleError("BAD_STATUS", "Only approved returns can be completed")
    if return_row.invoice_id is None:
        raise BusinessRuleError("NO_INVOICE", "Completion requires the original invoice")

    invoice = session.get(CustomerInvoice, return_row.invoice_id)
    if invoice is None or invoice.status != "posted":
        raise BusinessRuleError("INVOICE_NOT_POSTED", "Original invoice must be posted")

    # 1) quantity validation: return qty <= ordered + prior returns on same line
    prior_credit_lines = session.execute(
        select(SalesReturnLine).where(SalesReturnLine.return_id != return_row.id).filter(
            SalesReturnLine.return_id.in_(
                select(SalesReturn.id).where(
                    SalesReturn.order_id == return_row.order_id, SalesReturn.status == "completed"
                )
            )
        )
    ).scalars().all()
    prior_qtys: dict[str, Decimal] = {}
    for line in prior_credit_lines:
        prior_qtys[line.order_line_id] = prior_qtys.get(line.order_line_id, Decimal("0")) + dec(line.qty)
    from app.modules.sales import service as sales

    order_lines = {line.id: line for line in sales.get_order_lines(session, return_row.order_id)}
    lines = return_lines(session, return_row.id)
    for line in lines:
        ordered = dec(order_lines[line.order_line_id].qty)
        already = prior_qtys.get(line.order_line_id, Decimal("0"))
        if dec(line.qty) + already > ordered:
            raise BusinessRuleError(
                "OVER_RETURN",
                f"Return exceeds purchased qty for line {line.order_line_id}",
            )

    # 2) credit note (reverses revenue + tax on AR)
    company_id = return_row.company_id
    precision = 2
    credit_note = invoicing.create_credit_note(
        session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        invoice_id=invoice.id,
        lines=[
            {
                "invoice_line_id": _find_invoice_line(session, invoice.id, line.order_line_id),
                "qty": dec(line.qty),
                "description": f"Return {return_row.doc_number}",
                "tax_amount": Decimal("0"),
            }
            for line in lines
        ],
        note_date=(now or datetime.now(timezone.utc)).date(),
        reason=f"Sales return {return_row.doc_number}",
    )
    return_row.credit_note_id = credit_note.id

    # 3) stock disposition
    for line in lines:
        avg_cost = inventory.weighted_avg_cost(session, company_id, line.product_id)
        if line.disposition == "resalable":
            if not line.restock_location_id:
                raise BusinessRuleError(
                    "LOCATION_REQUIRED", f"restock_location_id required for resalable line {line.id}"
                )
            inventory.post_movement(
                session,
                company_id=company_id,
                movement_type="return_receipt",
                product_id=line.product_id,
                location_id=line.restock_location_id,
                quantity=dec(line.qty),
                unit_cost=avg_cost,
                source_type="sales_return",
                source_id=return_row.id,
                source_line_id=line.id,
                actor_user_id=actor_user_id,
            )
        elif line.disposition in ("damaged", "discarded"):
            # write-off: adjustment decrease at weighted average (loss booked to
            # returns/variance expense by the inventory service)
            inventory.adjust_stock(
                session,
                company_id=company_id,
                product_id=line.product_id,
                location_id=_any_stocked_location(session, company_id, line.product_id),
                quantity=dec(line.qty),
                direction="decrease",
                reason=f"Return {return_row.doc_number} {line.disposition}",
                actor_user_id=actor_user_id,
            )
        # quarantined: no movement; location/inspection handled out-of-band

    # 4) refund to customer via provider adapter
    refund_amount = money(sum((dec(line.qty) * dec(line.unit_price) for line in lines), Decimal("0")), precision)
    if refund_amount > 0:
        original_payment = session.scalar(
            select(PaymentRecord)
            .where(PaymentRecord.order_id == return_row.order_id, PaymentRecord.direction == "receipt", PaymentRecord.status == "succeeded")
            .order_by(PaymentRecord.occurred_at.desc())
        )
        if original_payment is None:
            raise BusinessRuleError("NO_ORIGINAL_PAYMENT", "No succeeded payment to refund against")
        refund = payments.provider_refund(
            session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            original=original_payment,
            amount=refund_amount,
        )
        refund.direction = "payment"  # it is money out
        session.flush()
        return_row.refund_payment_id = refund.id

    return_row.status = "completed"
    return_row.completed_at = now or datetime.now(timezone.utc)
    session.flush()
    return return_row


def _find_invoice_line(session: Session, invoice_id: str, order_line_id: str) -> str | None:
    from app.modules.sales.models import OrderLine

    order_line = session.get(OrderLine, order_line_id)
    if order_line is None:
        return None
    from app.modules.invoicing.models import InvoiceLine

    invoice_line = session.scalar(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id, InvoiceLine.product_id == order_line.product_id).order_by(InvoiceLine.line_number)
    )
    return invoice_line.id if invoice_line else None


def _any_stocked_location(session: Session, company_id: str, product_id: str) -> str | None:
    from app.modules.inventory.models import StockOnHand

    row = session.scalar(
        select(StockOnHand).where(StockOnHand.company_id == company_id, StockOnHand.product_id == product_id)
    )
    return row.location_id if row else None
