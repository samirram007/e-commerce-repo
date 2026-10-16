"""Inventory service: the only writer of stock ledger and on-hand rows.

Rules enforced here (AGENT.md §5.7, §6):
  * movements and their on-hand mirror are written in one transaction
  * negative stock is prevented unless the company setting allows it
  * weighted-average costing maintained in company base currency
  * reservations tracked separately from on-hand (overselling prevention)
"""
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Numeric, and_, func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import new_id
from app.modules.accounting import service as accounting
from app.modules.accounting.service import JournalLineSpec, SourceRef
from app.modules.companies.models import Company
from app.modules.inventory.models import (
    MOVEMENT_TYPES,
    ProductValuation,
    StockCount,
    StockCountLine,
    StockLedgerEntry,
    StockOnHand,
    StockTransfer,
)
from app.modules.storage import service as storage_svc
from app.shared.money import dec, money, qty as q4
from app.shared.numbering import allocate_number


def get_product_check(session: Session, product_id: str, company_id: str):
    """Validate the product exists and belongs to this company (IDOR guard)."""
    from app.modules.catalog.models import Product

    product = session.get(Product, product_id)
    if product is None or product.company_id != company_id:
        raise NotFoundError("Product")
    return product


def _company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    return company


def get_on_hand(session: Session, company_id: str, product_id: str, location_id: str, batch_ref: str | None) -> StockOnHand:
    row = session.scalar(
        select(StockOnHand).where(
            StockOnHand.company_id == company_id,
            StockOnHand.product_id == product_id,
            StockOnHand.location_id == location_id,
            StockOnHand.batch_ref == batch_ref,
        )
    )
    if row is None:
        row = StockOnHand(
            company_id=company_id, product_id=product_id, location_id=location_id, batch_ref=batch_ref,
            on_hand=Decimal("0"), reserved=Decimal("0"),
        )
        session.add(row)
        session.flush()
    return row


def get_valuation(session: Session, company_id: str, product_id: str) -> ProductValuation:
    row = session.scalar(
        select(ProductValuation).where(ProductValuation.company_id == company_id, ProductValuation.product_id == product_id)
    )
    if row is None:
        row = ProductValuation(
            company_id=company_id, product_id=product_id,
            avg_cost=Decimal("0"), total_qty=Decimal("0"), total_value=Decimal("0"),
        )
        session.add(row)
        session.flush()
    return row


def _ledger_entry(
    session: Session, **kwargs
) -> StockLedgerEntry:
    entry = StockLedgerEntry(moved_at=datetime.now(timezone.utc), **kwargs)
    session.add(entry)
    session.flush()
    return entry


def available_qty(row: StockOnHand) -> Decimal:
    return dec(row.on_hand) - dec(row.reserved)


def post_movement(
    session: Session,
    *,
    company_id: str,
    movement_type: str,
    product_id: str,
    location_id: str,
    quantity,  # signed delta
    unit_cost=None,
    batch_ref: str | None = None,
    expiry_date=None,
    source_type: str,
    source_id: str,
    source_line_id: str | None = None,
    actor_user_id: str | None = None,
) -> StockLedgerEntry:
    """Post one stock movement + mirror to on-hand (single transaction)."""
    if movement_type not in MOVEMENT_TYPES:
        raise BusinessRuleError("BAD_MOVEMENT_TYPE", f"movement_type must be one of {MOVEMENT_TYPES}")
    quantity = q4(dec(quantity))
    if quantity == 0:
        raise BusinessRuleError("ZERO_QTY", "Movement quantity must not be zero")
    storage_svc.get_location(session, company_id, location_id)  # validate location
    company = _company(session, company_id)

    row = get_on_hand(session, company_id, product_id, location_id, batch_ref)
    new_on_hand = dec(row.on_hand) + quantity
    if new_on_hand < 0 and not company.allow_negative_stock:
        raise BusinessRuleError(
            "NEGATIVE_STOCK",
            f"Movement would drive stock negative at this location (have {row.on_hand}, delta {quantity})",
        )

    unit_cost_value = None if unit_cost is None else money(dec(unit_cost), 2)
    entry = _ledger_entry(
        session,
        company_id=company_id,
        movement_type=movement_type,
        product_id=product_id,
        location_id=location_id,
        qty_delta=quantity,
        unit_cost=unit_cost_value,
        batch_ref=batch_ref,
        expiry_date=expiry_date,
        source_type=source_type,
        source_id=source_id,
        source_line_id=source_line_id,
        created_by=actor_user_id,
    )

    row.on_hand = money(new_on_hand, 4)
    if dec(row.on_hand) == 0 and dec(row.reserved) == 0 and row.id not in ("",):
        # keep the row (history/locking anchor) — zeroing is fine, no delete needed
        pass
    session.flush()

    # valuation book-keeping for stock-tracked products on real stock changes
    if movement_type in {"receipt", "return_receipt", "transfer_in", "adjustment", "issue", "transfer_out", "opening"}:
        _update_valuation(session, company_id, product_id, movement_type, abs(quantity), unit_cost_value)
    return entry


def _update_valuation(
    session: Session, company_id: str, product_id: str, movement_type: str, abs_q: Decimal, unit_cost: Decimal | None
) -> None:
    val = get_valuation(session, company_id, product_id)
    qty_total = dec(val.total_qty)
    value_total = dec(val.total_value)
    if movement_type in {"receipt", "return_receipt", "transfer_in", "opening"}:
        cost = dec(unit_cost or Decimal("0"))
        val.total_qty = money(qty_total + abs_q, 4)
        val.total_value = money(value_total + abs_q * cost, 2)
        if dec(val.total_qty) > 0:
            val.avg_cost = money(dec(val.total_value) / dec(val.total_qty), 4)
    elif movement_type in {"issue", "transfer_out", "adjustment"}:
        # issues at weighted average
        avg = dec(val.avg_cost)
        val.total_qty = money(qty_total - abs_q, 4)
        val.total_value = money(value_total - abs_q * avg, 2)
        if dec(val.total_qty) <= 0:
            val.total_qty = money(Decimal("0"), 4)
            val.total_value = money(Decimal("0"), 2)
    session.flush()


def weighted_avg_cost(session: Session, company_id: str, product_id: str) -> Decimal:
    return dec(get_valuation(session, company_id, product_id).avg_cost)


# ---- reservations (cart/checkout) ----
def check_availability(session: Session, *, company_id: str, product_id: str, location_id: str | None = None, need) -> bool:
    need = q4(dec(need))
    stmt = select(StockOnHand).where(StockOnHand.company_id == company_id, StockOnHand.product_id == product_id)
    if location_id:
        ids = storage_svc.bin_ids_under(session, company_id, location_id) if location_id else {location_id}
        stmt = stmt.where(StockOnHand.location_id.in_(ids or [location_id]))
    total = Decimal("0")
    for row in session.execute(stmt).scalars():
        total += available_qty(row)
    return total >= need


def reserve_stock(
    session: Session, *, company_id: str, product_id: str, quantity: Decimal, source_type: str, source_id: str,
    location_id: str | None = None, actor_user_id: str | None = None,
) -> None:
    """Reserve from a single location with available stock (raises if short)."""
    quantity = q4(dec(quantity))
    stmt = select(StockOnHand).where(
        StockOnHand.company_id == company_id, StockOnHand.product_id == product_id
    )
    if location_id:
        ids = storage_svc.bin_ids_under(session, company_id, location_id)
        stmt = stmt.where(StockOnHand.location_id.in_(ids or [location_id]))
    candidates = session.execute(stmt).scalars().all()
    candidates.sort(key=lambda r: available_qty(r), reverse=True)
    remaining = quantity
    for row in candidates:
        avail = available_qty(row)
        if avail <= 0:
            continue
        take = min(avail, remaining)
        row.reserved = money(dec(row.reserved) + take, 4)
        _ledger_entry(
            session,
            company_id=company_id,
            movement_type="reserve",
            product_id=product_id,
            location_id=row.location_id,
            qty_delta=take,
            batch_ref=row.batch_ref,
            source_type=source_type,
            source_id=source_id,
            created_by=actor_user_id,
        )
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        raise BusinessRuleError(
            "INSUFFICIENT_STOCK",
            f"Cannot reserve {quantity}: insufficient stock for this product",
        )
    session.flush()


def release_reservation(
    session: Session, *, company_id: str, product_id: str, quantity, source_type: str, source_id: str,
    actor_user_id: str | None = None,
) -> Decimal:
    """Release a prior reservation; returns the released total."""
    quantity = q4(dec(quantity))
    rows = session.execute(
        select(StockOnHand).where(StockOnHand.company_id == company_id, StockOnHand.product_id == product_id)
    ).scalars().all()
    rows.sort(key=lambda r: dec(r.reserved), reverse=True)
    remaining = quantity
    released = Decimal("0")
    for row in rows:
        if remaining <= 0:
            break
        take = min(dec(row.reserved), remaining)
        if take <= 0:
            continue
        row.reserved = money(dec(row.reserved) - take, 4)
        _ledger_entry(
            session,
            company_id=company_id,
            movement_type="release",
            product_id=product_id,
            location_id=row.location_id,
            qty_delta=-take,
            batch_ref=row.batch_ref,
            source_type=source_type,
            source_id=source_id,
            created_by=actor_user_id,
        )
        released += take
        remaining -= take
    if remaining > 0:
        raise BusinessRuleError("RESERVATION_MISMATCH", "Not enough reserved stock to release")
    session.flush()
    return released


# ---- transfers ----
def transfer_stock(
    session: Session, *, company_id: str, from_location_id: str, to_location_id: str,
    product_id: str, quantity, source_type: str = "transfer", source_id: str | None = None,
    actor_user_id: str | None = None, write_gl: bool = True, description: str | None = None,
) -> str:
    """Move stock between two bin-level locations within the same warehouse.
    Writes two ledger entries (out at avg cost + in at same cost)."""
    quantity = q4(dec(quantity))
    if quantity <= 0:
        raise BusinessRuleError("BAD_QTY", "Transfer quantity must be > 0")
    origin = storage_svc.get_location(session, company_id, from_location_id)
    destination = storage_svc.get_location(session, company_id, to_location_id)
    if origin.id == destination.id:
        raise BusinessRuleError("SAME_LOCATION", "Source and destination must differ")
    if origin.company_id != company_id or destination.company_id != company_id:
        raise BusinessRuleError("CROSS_COMPANY_MOVE", "Both locations must belong to the company")
    if origin.location_type != "bin" or destination.location_type != "bin":
        raise BusinessRuleError("BIN_REQUIRED", "Transfers move stock between bin-level locations")
    source_id = source_id or new_id()
    avg_cost = weighted_avg_cost(session, company_id, product_id)

    on_hand_source = dec(get_on_hand(session, company_id, product_id, origin.id, None).on_hand)
    if on_hand_source < quantity:
        raise BusinessRuleError("INSUFFICIENT_STOCK", f"Only {on_hand_source} on hand at source")

    out_entry = post_movement(
        session,
        company_id=company_id,
        movement_type="transfer_out",
        product_id=product_id,
        location_id=origin.id,
        quantity=-quantity,
        unit_cost=avg_cost,
        source_type=source_type,
        source_id=source_id,
        actor_user_id=actor_user_id,
    )
    in_entry = post_movement(
        session,
        company_id=company_id,
        movement_type="transfer_in",
        product_id=product_id,
        location_id=destination.id,
        quantity=quantity,
        unit_cost=avg_cost,
        source_type=source_type,
        source_id=source_id,
        actor_user_id=actor_user_id,
    )
    out_entry.counter_entry_id = in_entry.id
    in_entry.counter_entry_id = out_entry.id
    session.flush()

    if write_gl:
        transfer_value = money(quantity * avg_cost, 2)
        codes = accounting.account_code_map(session, company_id)
        if transfer_value != 0:
            accounting.post_journal_entry(
                session,
                company_id=company_id,
                entry_date=datetime.now(timezone.utc).date(),
                source=SourceRef(type=source_type, id=source_id),
                lines=[
                    JournalLineSpec(account_code=codes["inventory"], side="debit", amount_base=transfer_value, description=f"Transfer in to {destination.code}"),
                    JournalLineSpec(account_code=codes["inventory"], side="credit", amount_base=transfer_value, description=f"Transfer out of {origin.code}"),
                ],
                description=description or f"Stock transfer qty {quantity}",
                actor_user_id=actor_user_id,
            )
    return source_id


# ---- adjustments & counts ----
def adjust_stock(
    session: Session, *, company_id: str, product_id: str, location_id: str, quantity,
    direction: str = "increase", reason: str | None = None, actor_user_id: str | None = None,
) -> dict:
    """Stock adjustment with GL posting: variance/null instruction."""
    quantity = q4(dec(quantity))
    if quantity <= 0:
        raise BusinessRuleError("BAD_QTY", "Adjustment quantity must be > 0")
    avg_cost = weighted_avg_cost(session, company_id, product_id)
    delta = quantity if direction == "increase" else -quantity
    if direction == "decrease":
        row = get_on_hand(session, company_id, product_id, location_id, None)
        if dec(row.on_hand) < quantity:
            raise BusinessRuleError("INSUFFICIENT_STOCK", "Cannot decrease below on-hand")
    entry = post_movement(
        session,
        company_id=company_id,
        movement_type="adjustment",
        product_id=product_id,
        location_id=location_id,
        quantity=delta,
        unit_cost=avg_cost,
        source_type="stock_adjustment",
        source_id=new_id(),
        actor_user_id=actor_user_id,
    )
    value = money(quantity * avg_cost, 2)
    codes = accounting.account_code_map(session, company_id)
    if value != 0:
        variance_account = codes["inventory_variance"]
        if direction == "increase":
            lines = [
                JournalLineSpec(account_code=codes["inventory"], side="debit", amount_base=value, description=reason),
                JournalLineSpec(account_code=variance_account, side="credit", amount_base=value, description=reason),
            ]
        else:
            lines = [
                JournalLineSpec(account_code=variance_account, side="debit", amount_base=value, description=reason),
                JournalLineSpec(account_code=codes["inventory"], side="credit", amount_base=value, description=reason),
            ]
        accounting.post_journal_entry(
            session,
            company_id=company_id,
            entry_date=datetime.now(timezone.utc).date(),
            source=SourceRef(type="stock_adjustment", id=entry.source_id),
            lines=lines,
            description=reason or "Stock adjustment",
            actor_user_id=actor_user_id,
        )
    return {"ledger_entry_id": entry.id, "value": str(value), "avg_cost": str(avg_cost)}


def create_count(session: Session, *, company_id: str, location_id: str, actor_user_id: str) -> StockCount:
    doc_number = allocate_number(session, company_id, "stock_adjustment")
    count = StockCount(company_id=company_id, doc_number=doc_number, location_id=location_id, status="open", created_by=actor_user_id)
    session.add(count)
    session.flush()
    return count


def add_count_line(session: Session, count: StockCount, *, product_id: str, counted_qty) -> StockCountLine:
    company_id = count.company_id
    system_total = Decimal("0")
    for row in session.execute(
        select(StockOnHand).where(StockOnHand.company_id == company_id, StockOnHand.product_id == product_id)
    ).scalars():
        system_total += dec(row.on_hand)
    line = StockCountLine(
        count_id=count.id,
        product_id=product_id,
        counted_qty=q4(dec(counted_qty)),
        system_qty=system_total,
        variance=q4(dec(counted_qty) - system_total),
    )
    session.add(line)
    session.flush()
    return line


def post_count(session: Session, count: StockCount, actor_user_id: str) -> dict:
    """Post a count: variance movements + value reconciliation to inventory variance."""
    if count.status != "open":
        raise BusinessRuleError("COUNT_NOT_OPEN", "Only open counts can be posted")
    lines = session.execute(select(StockCountLine).where(StockCountLine.count_id == count.id)).scalars().all()
    variance_value = Decimal("0")
    codes = accounting.account_code_map(session, count.company_id)
    avg_cost_default = None
    for line in lines:
        variance = dec(line.variance)
        if variance == 0:
            continue
        product_avg = weighted_avg_cost(session, count.company_id, line.product_id)
        if variance > 0:
            post_movement(
                session,
                company_id=count.company_id,
                movement_type="adjustment",
                product_id=line.product_id,
                location_id=count.location_id,
                quantity=variance,
                unit_cost=product_avg,
                source_type="stock_count",
                source_id=count.id,
                actor_user_id=actor_user_id,
            )
        else:
            post_movement(
                session,
                company_id=count.company_id,
                movement_type="adjustment",
                product_id=line.product_id,
                location_id=count.location_id,
                quantity=variance,
                unit_cost=product_avg,
                source_type="stock_count",
                source_id=count.id,
                actor_user_id=actor_user_id,
            )
        variance_value += variance * product_avg
    variance_value = money(variance_value, 2)
    if variance_value != 0:
        side = "credit" if variance_value > 0 else "debit"
        opposite = "debit" if side == "credit" else "credit"
        accounting.post_journal_entry(
            session,
            company_id=count.company_id,
            entry_date=datetime.now(timezone.utc).date(),
            source=SourceRef(type="stock_count", id=count.id),
            lines=[
                JournalLineSpec(account_code=codes["inventory"], side=opposite if side == "debit" else "debit", amount_base=abs(variance_value), description=f"Count variance {count.doc_number}"),
                JournalLineSpec(account_code=codes["inventory_variance"], side=side if side == "debit" else "credit", amount_base=abs(variance_value), description=f"Count variance {count.doc_number}"),
            ],
            description=f"Stock count variance {count.doc_number}",
            actor_user_id=actor_user_id,
        )
    count.status = "posted"
    session.flush()
    return {"variance_value": str(variance_value)}


def has_open_variances(session: Session, company_id: str) -> bool:
    """Placeholder for year-end control: open (unposted) counts do not block
    closing by default; kept as named query hook."""
    counts = session.execute(
        select(func.count()).select_from(StockCount).where(StockCount.company_id == company_id, StockCount.status == "open")
    )
    return (counts.scalar() or 0) > 0


# ---- views ----
def stock_on_hand_view(session: Session, company_id: str, *, product_id: str | None = None, location_id: str | None = None):
    stmt = select(StockOnHand).where(StockOnHand.company_id == company_id)
    if product_id:
        stmt = stmt.where(StockOnHand.product_id == product_id)
    if location_id:
        bins = storage_svc.bin_ids_under(session, company_id, location_id)
        stmt = stmt.where(StockOnHand.location_id.in_(bins or [location_id]))
    stmt = stmt.order_by(StockOnHand.product_id, StockOnHand.location_id)
    return session.execute(stmt).scalars().all()


def stock_ledger_view(session: Session, company_id: str, *, product_id: str | None, location_id: str | None, limit: int = 1000):
    from app.modules.catalog.models import Product
    from app.modules.storage.models import StorageLocation

    stmt = (
        select(StockLedgerEntry, Product.sku, StorageLocation.code)
        .join(Product, StockLedgerEntry.product_id == Product.id)
        .join(StorageLocation, StockLedgerEntry.location_id == StorageLocation.id)
        .where(StockLedgerEntry.company_id == company_id)
        .order_by(StockLedgerEntry.moved_at.desc(), StockLedgerEntry.id.desc())
        .limit(limit)
    )
    if product_id:
        stmt = stmt.where(StockLedgerEntry.product_id == product_id)
    if location_id:
        bins = storage_svc.bin_ids_under(session, company_id, location_id)
        stmt = stmt.where(StockLedgerEntry.location_id.in_(bins or [location_id]))
    return session.execute(stmt).all()


def reconcile_check(session: Session, company_id: str) -> bool:
    """Invariant: on-hand equals sum of ledger deltas per (product, location, batch)."""
    ledger_sums = {}
    stmt = select(
        StockLedgerEntry.product_id,
        StockLedgerEntry.location_id,
        StockLedgerEntry.batch_ref,
        func.sum(StockLedgerEntry.qty_delta),
    ).where(StockLedgerEntry.company_id == company_id).group_by(
        StockLedgerEntry.product_id, StockLedgerEntry.location_id, StockLedgerEntry.batch_ref
    )
    for product_id, location_id, batch_ref, total in session.execute(stmt):
        ledger_sums[(product_id, location_id, batch_ref)] = dec(total)
    on_hand_rows = session.execute(select(StockOnHand).where(StockOnHand.company_id == company_id)).scalars().all()
    for row in on_hand_rows:
        key = (row.product_id, row.location_id, row.batch_ref)
        if key not in ledger_sums:
            if dec(row.on_hand) != 0:
                return False
        elif dec(row.on_hand) != ledger_sums[key]:
            return False
    return True


def stock_valuation_report(session: Session, company_id: str) -> list[dict]:
    from app.modules.catalog.models import Product

    stmt = select(ProductValuation, Product.sku).join(Product, ProductValuation.product_id == Product.id).where(ProductValuation.company_id == company_id).order_by(Product.sku)
    return [
        {
            "product_id": val.product_id,
            "sku": sku,
            "avg_cost": str(val.avg_cost),
            "total_qty": str(val.total_qty),
            "total_value": str(val.total_value),
        }
        for val, sku in session.execute(stmt).all()
    ]
