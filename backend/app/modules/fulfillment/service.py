"""Fulfillment service: shipment lifecycle with an enforced status machine.

Delivering requires the carrier webhook — never the dispatch call alone.
Stock is issued (inventory ledger + COGS journal) when the shipment leaves
picking as packed, at weighted-average cost.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.accounting import service as accounting
from app.modules.accounting.service import JournalLineSpec, SourceRef
from app.modules.delivery import adapters as carriers
from app.modules.fulfillment.models import SHIPMENT_STATUSES, Shipment, ShipmentLine
from app.modules.inventory import service as inventory
from app.modules.sales import service as sales
from app.modules.sales.models import SalesOrder
from app.shared.money import dec, money
from app.shared.numbering import allocate_number

LEGAL_TRANSITIONS = {
    "created": {"picking", "cancelled_shipment"},
    "picking": {"picked"},
    "picked": {"packed"},
    "packed": {"dispatched"},
    "dispatched": {"in_transit"},
    "in_transit": {"delivered", "failed"},
    "failed": {"returned_to_origin", "in_transit"},
    "returned_to_origin": {"delivered"},
    "delivered": set(),
}
COGS_POSTED_AT = "picked"


def get_shipment(session: Session, company_id: str, shipment_id: str) -> Shipment:
    shipment = session.get(Shipment, shipment_id)
    if shipment is None or shipment.company_id != company_id:
        raise NotFoundError("Shipment")
    return shipment


def get_shipment_lines(session: Session, shipment_id: str) -> list[ShipmentLine]:
    return list(
        session.execute(select(ShipmentLine).where(ShipmentLine.shipment_id == shipment_id)).scalars()
    )


def create_shipment(
    session: Session, *, company_id: str, actor_user_id: str, order_id: str
) -> Shipment:
    """Create a shipment from a paid order; opens picking from reserved lines."""
    order = sales.get_order(session, company_id, order_id)
    if order.status not in ("paid", "confirmed"):
        raise BusinessRuleError("ORDER_NOT_FULFILLABLE", f"Order status '{order.status}' cannot be fulfilled")
    if session.scalar(select(Shipment.id).where(Shipment.order_id == order.id, Shipment.status != "returned_to_origin")):
        raise BusinessRuleError("SHIPMENT_EXISTS", "An active shipment already exists for this order")
    doc_number = allocate_number(session, company_id, "shipment")
    shipment = Shipment(
        company_id=company_id,
        doc_number=doc_number,
        order_id=order.id,
        status="picking",
        shipping_address_snapshot=order.shipping_address,
        created_by=actor_user_id,
    )
    session.add(shipment)
    session.flush()
    for line in sales.get_order_lines(session, order.id):
        if line.reserved_location_id is None:
            continue  # services/non-stock lines are not shipped
        session.add(
            ShipmentLine(
                shipment_id=shipment.id,
                order_line_id=line.id,
                product_id=line.product_id,
                from_location_id=line.reserved_location_id,
                qty=line.qty,
            )
        )
    order.status = "fulfilling"
    session.flush()
    return shipment


def transition_shipment(
    session: Session, company_id: str, shipment_id: str, to_status: str, actor_user_id: str | None
) -> Shipment:
    shipment = get_shipment(session, company_id, shipment_id)
    if to_status not in LEGAL_TRANSITIONS.get(shipment.status, set()):
        raise BusinessRuleError(
            "BAD_SHIPMENT_TRANSITION", f"Cannot move shipment from '{shipment.status}' to '{to_status}'"
        )
    prev = shipment.status
    shipment.status = to_status
    if to_status == "picking":
        shipment.picked_by = actor_user_id
    elif to_status == "packed":
        shipment.packed_by = actor_user_id
        _issue_cogs(session, shipment, actor_user_id)
        order = sales.get_order(session, company_id, shipment.order_id)
        _issue_reserved_stock(session, shipment, actor_user_id)
        order.status = "fulfilled"
    elif to_status == "dispatched":
        shipment.dispatched_at = datetime.now(timezone.utc)
        order = sales.get_order(session, company_id, shipment.order_id)
        order.status = "shipped"
    elif to_status == "delivered":
        shipment.delivered_at = datetime.now(timezone.utc)
        order = session.get(SalesOrder, shipment.order_id)
        if order is not None:
            order.status = "delivered"
            # Cash on delivery is collected now; prepaid orders already settled.
            sales.collect_cash_on_delivery(session, order=order)
    session.flush()
    return shipment


def _issue_reserved_stock(session: Session, shipment: Shipment, actor_user_id: str | None) -> None:
    """Convert reservations into stock issues for this shipment's lines.

    Issues follow the exact rows `release_reservation` consumed (location and
    batch_ref), so batch-tracked products decrement their batch row instead of
    the batch_ref=None row, which would drive on-hand negative.
    """
    for line in get_shipment_lines(session, shipment.id):
        plan = inventory.release_reservation(
            session,
            company_id=shipment.company_id,
            product_id=line.product_id,
            quantity=line.qty,
            source_type="sales_order_fulfill",
            source_id=shipment.order_id,
            actor_user_id=actor_user_id,
        )
        avg_cost = inventory.weighted_avg_cost(session, shipment.company_id, line.product_id)
        for location_id, batch_ref, take in plan:
            inventory.post_movement(
                session,
                company_id=shipment.company_id,
                movement_type="issue",
                product_id=line.product_id,
                location_id=location_id,
                quantity=-take,
                batch_ref=batch_ref,
                unit_cost=avg_cost,
                source_type="shipment",
                source_id=shipment.id,
                source_line_id=line.id,
                actor_user_id=actor_user_id,
            )


def _issue_cogs(session: Session, shipment: Shipment, actor_user_id: str | None) -> None:
    """COGS journal when the goods physically leave the warehouse (packed)."""
    company_id = shipment.company_id
    total_cost = Decimal("0")
    from app.core.exceptions import NotFoundError as _NF
    from app.modules.companies.models import Company

    company = session.get(Company, company_id)
    if company is None:
        raise _NF("Company")
    lines = get_shipment_lines(session, shipment.id)
    precision = 2
    for line in lines:
        avg_cost = inventory.weighted_avg_cost(session, company_id, line.product_id)
        total_cost += dec(line.qty) * avg_cost
    total_cost = money(total_cost, precision)
    if total_cost == 0:
        return
    codes = accounting.account_code_map(session, company_id)
    accounting.post_journal_entry(
        session,
        company_id=company_id,
        entry_date=datetime.now(timezone.utc).date(),
        source=SourceRef(type="shipment", id=shipment.id),
        lines=[
            JournalLineSpec(account_code=codes["cogs"], side="debit", amount_base=total_cost, description=f"COGS shipment {shipment.doc_number}"),
            JournalLineSpec(account_code=codes["inventory"], side="credit", amount_base=total_cost, description=f"COGS shipment {shipment.doc_number}"),
        ],
        description=f"COGS for shipment {shipment.doc_number}",
        actor_user_id=actor_user_id,
    )


def carrier_dispatch(
    session: Session, shipment: Shipment, *, carrier_name: str = "mock", actor_user_id: str | None
) -> Shipment:
    """Dispatch via carrier adapter; moves packed -> dispatched and records
    tracking. Delivery is later confirmed by the carrier webhook."""
    if shipment.status != "packed":
        raise BusinessRuleError("NOT_PACKED", "Only packed shipments can be dispatched")
    adapter = carriers.get_carrier_adapter(carrier_name)
    result = adapter.dispatch(shipment_ref=shipment.id, address=shipment.shipping_address_snapshot or "")
    shipment.carrier_code = adapter.name
    shipment.carrier_name = adapter.name
    shipment.tracking_number = result.tracking_number
    session.flush()
    transition_shipment(session, shipment.company_id, shipment.id, "dispatched", actor_user_id)
    transition_shipment(session, shipment.company_id, shipment.id, "in_transit", actor_user_id)
    return shipment


def confirm_carrier_delivery(
    session: Session, *, company_id: str, tracking_number: str, signature: str, payload: dict
) -> Shipment:
    """Carrier webhook: verify signature, find shipment by tracking number,
    mark delivered idempotently (event deduped in idempotency store)."""
    import hashlib
    import hmac as hmac_mod
    import json

    from app.core.config import get_settings
    from app.shared.idempotency import run_idempotent

    raw = json.dumps(payload, sort_keys=True).encode()
    expected = hmac_mod.new(get_settings().secret_key.encode(), raw, hashlib.sha256).hexdigest()
    ok = hmac_mod.compare_digest(signature, expected)
    if not ok:
        raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Carrier webhook signature failed")
    shipment = session.scalar(
        select(Shipment).where(Shipment.company_id == company_id, Shipment.tracking_number == tracking_number)
    )
    if shipment is None:
        raise NotFoundError("Shipment")
    event_id = str(payload.get("event_id", ""))

    def _apply() -> dict:
        if shipment.status != "delivered":
            transition_shipment(session, company_id, shipment.id, "delivered", None)
        return {"shipment_id": shipment.id, "status": shipment.status}

    result, replayed = run_idempotent(
        session,
        scope=f"carrier_webhook:{company_id}",
        key=f"delivery:{event_id or tracking_number}",
        company_id=company_id,
        execute=_apply,
    )
    return session.get(Shipment, result["shipment_id"])
