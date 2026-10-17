"""Inventory HTTP routes: on-hand, ledger, transfers, adjustments, counts."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import P_INVENTORY_MANAGE, P_INVENTORY_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.inventory import service as svc
from app.modules.inventory.models import StockCount, StockCountLine, StockTransfer
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/inventory")


class TransferIn(BaseModel):
    product_id: str
    from_location_id: str
    to_location_id: str
    quantity: Decimal = Field(gt=0)


class AdjustIn(BaseModel):
    location_id: str
    product_id: str
    quantity: Decimal = Field(gt=0)
    direction: str = "increase"
    reason: str | None = None


class CountLineIn(BaseModel):
    product_id: str
    counted_qty: Decimal


class CountCreateIn(BaseModel):
    location_id: str


@router.get("/on-hand")
def on_hand(
    product_id: str | None = None,
    location_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.stock_on_hand_view(session, ctx.company_id, product_id=product_id, location_id=location_id)
    return [
        {
            "product_id": r.product_id,
            "location_id": r.location_id,
            "batch_ref": r.batch_ref,
            "on_hand": str(r.on_hand),
            "reserved": str(r.reserved),
            "available": str(svc.available_qty(r)),
        }
        for r in rows
    ]


@router.get("/ledger")
def ledger(
    product_id: str | None = None,
    location_id: str | None = None,
    limit: int = 200,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.stock_ledger_view(session, ctx.company_id, product_id=product_id, location_id=location_id, limit=min(limit, 1000))
    return [
        {
            "id": e.id,
            "movement_type": e.movement_type,
            "sku": sku,
            "location_code": loc_code,
            "qty_delta": str(e.qty_delta),
            "unit_cost": None if e.unit_cost is None else str(e.unit_cost),
            "batch_ref": e.batch_ref,
            "source_type": e.source_type,
            "source_id": e.source_id,
            "moved_at": e.moved_at.isoformat(),
        }
        for e, sku, loc_code in rows
    ]


@router.post("/transfers", status_code=201)
def transfer(
    payload: TransferIn,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)),
    session: Session = Depends(get_db),
):
    svc.get_product_check(session, payload.product_id, ctx.company_id)
    transfer_id = svc.transfer_stock(
        session,
        company_id=ctx.company_id,
        from_location_id=payload.from_location_id,
        to_location_id=payload.to_location_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        actor_user_id=ctx.user.id,
    )
    session.add(
        StockTransfer(
            company_id=ctx.company_id,
            doc_number=transfer_id[:12],
            status="done",
            lines="[]",
            transfer_ref=transfer_id,
        )
    )
    log_action(
        session, action="stock.transferred", entity_type="stock_transfer",
        entity_id=transfer_id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return {"transfer_id": transfer_id}


@router.post("/adjustments", status_code=201)
def adjust(
    payload: AdjustIn,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)),
    session: Session = Depends(get_db),
):
    svc.get_product_check(session, payload.product_id, ctx.company_id)
    result = svc.adjust_stock(
        session,
        company_id=ctx.company_id,
        product_id=payload.product_id,
        location_id=payload.location_id,
        quantity=payload.quantity,
        direction=payload.direction,
        reason=payload.reason,
        actor_user_id=ctx.user.id,
    )
    log_action(
        session, action="stock.adjusted", entity_type="stock_adjustment",
        entity_id=result["ledger_entry_id"], actor_user_id=ctx.user.id,
        company_id=ctx.company_id, after_data=result,
    )
    return result


@router.post("/counts", status_code=201)
def create_count(
    payload: CountCreateIn,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)),
    session: Session = Depends(get_db),
):
    count = svc.create_count(session, company_id=ctx.company_id, location_id=payload.location_id, actor_user_id=ctx.user.id)
    log_action(session, action="stock_count.created", entity_type="stock_count", entity_id=count.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return {"id": count.id, "doc_number": count.doc_number, "status": count.status}


@router.get("/counts/{count_id}")
def get_count(count_id: str, ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)), session: Session = Depends(get_db)):
    from app.core.exceptions import NotFoundError

    count = session.get(StockCount, count_id)
    if count is None or count.company_id != ctx.company_id:
        raise NotFoundError("Stock count")
    lines = session.execute(
        StockCountLine.__table__.select().where(StockCountLine.count_id == count.id)
    ).mappings().all()
    return {
        "id": count.id,
        "doc_number": count.doc_number,
        "location_id": count.location_id,
        "status": count.status,
        "lines": [
            {"id": l["id"], "product_id": l["product_id"], "counted_qty": str(l["counted_qty"]), "system_qty": str(l["system_qty"]), "variance": str(l["variance"])}
            for l in lines
        ],
    }


@router.post("/counts/{count_id}/lines", status_code=201)
def add_count_line(
    count_id: str,
    payload: CountLineIn,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)),
    session: Session = Depends(get_db),
):
    from app.core.exceptions import BusinessRuleError, NotFoundError

    count = session.get(StockCount, count_id)
    if count is None or count.company_id != ctx.company_id:
        raise NotFoundError("Stock count")
    if count.status != "open":
        raise BusinessRuleError("COUNT_NOT_OPEN", "Count is not open")
    line = svc.add_count_line(session, count, product_id=payload.product_id, counted_qty=payload.counted_qty)
    return {"id": line.id, "variance": str(line.variance)}


@router.post("/counts/{count_id}/post")
def post_count(count_id: str, ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)), session: Session = Depends(get_db)):
    from app.core.exceptions import NotFoundError

    count = session.get(StockCount, count_id)
    if count is None or count.company_id != ctx.company_id:
        raise NotFoundError("Stock count")
    result = svc.post_count(session, count, ctx.user.id)
    log_action(
        session, action="stock_count.posted", entity_type="stock_count",
        entity_id=count.id, actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data=result,
    )
    return {"id": count.id, "status": count.status, "variance_value": result["variance_value"]}


@router.get("/valuation")
def valuation(ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)), session: Session = Depends(get_db)):
    return svc.stock_valuation_report(session, ctx.company_id)


@router.get("/serials")
def serials(
    product_id: str | None = None,
    location_id: str | None = None,
    status: str | None = None,
    batch_ref: str | None = None,
    search: str | None = None,
    limit: int = 500,
    ctx: CompanyCtx = Depends(guard(P_INVENTORY_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.serials_view(
        session,
        ctx.company_id,
        product_id=product_id,
        location_id=location_id,
        status=status,
        batch_ref=batch_ref,
        search=search,
        limit=limit,
    )
    return [
        {
            "id": s.id,
            "product_id": s.product_id,
            "sku": sku,
            "location_id": s.location_id,
            "location_code": loc_code,
            "batch_ref": s.batch_ref,
            "serial_number": s.serial_number,
            "status": s.status,
            "source_type": s.source_type,
            "source_id": s.source_id,
            "created_at": s.created_at.isoformat(),
            "issued_at": s.issued_at.isoformat() if s.issued_at else None,
        }
        for s, sku, loc_code in rows
    ]


@router.get("/reconcile")
def reconcile(ctx: CompanyCtx = Depends(guard(P_INVENTORY_MANAGE)), session: Session = Depends(get_db)):
    ok = svc.reconcile_check(session, ctx.company_id)
    return {"balanced": ok}
