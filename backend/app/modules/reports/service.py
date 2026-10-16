"""Reports service: operational aggregates with explicit date boundaries.

Date ranges are interpreted in the company timezone as inclusive bounds on
business dates; note the boundaries in each query docstring.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.companies.models import Company
from app.shared.money import dec, money


def company_tz(session: Session, company_id: str) -> ZoneInfo:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    try:
        return ZoneInfo(company.timezone)
    except Exception:
        return ZoneInfo("UTC")


def to_utc_day_bounds(session: Session, company_id: str, from_date: date | None, to_date: date | None):
    """Inclusive midnight-to-midnight window in company timezone -> UTC bounds."""
    tz = company_tz(session, company_id)
    start_local = datetime.combine(from_date or date.today(), datetime.min.time(), tzinfo=tz)
    end_local = datetime.combine((to_date or from_date or date.today()), datetime.min.time(), tzinfo=tz) + timedelta(days=1) - timedelta(microseconds=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def sales_summary(session: Session, company_id: str, *, from_date: date | None, to_date: date | None) -> dict:
    from app.modules.invoicing.models import CustomerInvoice

    stmt = select(
        func.count(CustomerInvoice.id).label("n"),
        func.sum(CustomerInvoice.total).label("total"),
        func.sum(CustomerInvoice.tax_total).label("tax"),
    ).where(CustomerInvoice.company_id == company_id, CustomerInvoice.status == "posted")
    if from_date:
        stmt = stmt.where(CustomerInvoice.invoice_date >= from_date)
    if to_date:
        stmt = stmt.where(CustomerInvoice.invoice_date <= to_date)
    row = session.execute(stmt).one()
    return {
        "invoice_count": int(row.n or 0),
        "total": str(row.total or "0"),
        "tax_total": str(row.tax or "0"),
    }


def purchase_summary(session: Session, company_id: str, *, from_date: date | None, to_date: date | None) -> dict:
    from app.modules.purchasing.models import VendorBill

    stmt = select(
        func.count(VendorBill.id).label("n"),
        func.sum(VendorBill.total).label("total"),
    ).where(VendorBill.company_id == company_id, VendorBill.status == "posted")
    if from_date:
        stmt = stmt.where(VendorBill.bill_date >= from_date)
    if to_date:
        stmt = stmt.where(VendorBill.bill_date <= to_date)
    row = session.execute(stmt).one()
    return {"bill_count": int(row.n or 0), "total": str(row.total or "0")}


def delivery_performance(session: Session, company_id: str, *, from_date: date | None, to_date: date | None) -> dict:
    from app.modules.fulfillment.models import Shipment

    stmt = select(Shipment.status, func.count(Shipment.id)).where(Shipment.company_id == company_id)
    stmt = stmt.group_by(Shipment.status)
    statuses = {status: int(n) for status, n in session.execute(stmt).all()}
    delivered = statuses.get("delivered", 0)
    failed = statuses.get("failed", 0)
    total = sum(statuses.values())
    return {
        "statuses": statuses,
        "on_time_rate": str(money(Decimal(delivered) / Decimal(total) * 100, 2) if total else "0"),
        "failure_count": failed,
    }


def stock_valuation(session: Session, company_id: str) -> list[dict]:
    from app.modules.inventory import service as inventory

    return inventory.stock_valuation_report(session, company_id)
