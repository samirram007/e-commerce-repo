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


def gst_summary(session: Session, company_id: str, *, from_date: date | None = None, to_date: date | None = None) -> dict:
    """GST summary per period: net output CGST/SGST (2110/2120) against
    input CGST/SGST (1160/1170) tax credits.

    Returns a dict with per-date breakdown and a grand total.
    """
    from app.modules.accounting.models import Account, JournalEntry, JournalLine

    stmt = (
        select(
            JournalEntry.entry_date,
            Account.code,
            JournalLine.side,
            func.sum(JournalLine.amount).label("total"),
        )
        .join(JournalLine, JournalEntry.id == JournalLine.entry_id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "posted")
    )
    if from_date:
        stmt = stmt.where(JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(JournalEntry.entry_date <= to_date)
    rows = session.execute(
        stmt.group_by(JournalEntry.entry_date, Account.code, JournalLine.side)
    ).all()
    # Accumulate per-date tallies for the four GST accounts
    by_date: dict[str, dict[str, Decimal]] = {}
    for entry_date, code, side, total in rows:
        d = by_date.setdefault(entry_date.isoformat(), {"2110": Decimal("0"), "2120": Decimal("0"), "1160": Decimal("0"), "1170": Decimal("0")})
        if code in {"2110", "2120", "1160", "1170"}:
            by_date[entry_date.isoformat()][code] += dec(total)
    # Build per-date net summaries
    out = []
    for date_str in sorted(by_date):
        d = by_date[date_str]
        total_out_cgst = d["2110"]
        total_out_sgst = d["2120"]
        total_in_cgst = d["1160"]
        total_in_sgst = d["1170"]
        net_cgst = total_out_cgst - total_in_cgst
        net_sgst = total_out_sgst - total_in_sgst
        out.append({
            "date": date_str,
            "output_cgst": str(total_out_cgst),
            "output_sgst": str(total_out_sgst),
            "input_cgst": str(total_in_cgst),
            "input_sgst": str(total_in_sgst),
            "net_cgst": str(net_cgst),
            "net_sgst": str(net_sgst),
        })
    # Aggregate across the whole period
    if out:
        grand = {
            "output_cgst": "0",
            "output_sgst": "0",
            "input_cgst": "0",
            "input_sgst": "0",
            "net_cgst": "0",
            "net_sgst": "0",
        }
        for row in out:
            for key in grand:
                if key in row and row[key] != "":
                    grand[key] = str(Decimal(grand[key]) + Decimal(row[key]))
        return {
            "period_from": from_date.isoformat() if from_date else None,
            "period_to": to_date.isoformat() if to_date else None,
            "summary": out,
            "grand_total": grand,
        }
    return {
        "period_from": from_date.isoformat() if from_date else None,
        "period_to": to_date.isoformat() if to_date else None,
        "summary": out,
        "grand_total": {
            "output_cgst": "0",
            "output_sgst": "0",
            "input_cgst": "0",
            "input_sgst": "0",
            "net_cgst": "0",
            "net_sgst": "0",
        },
    }


def stock_valuation(session: Session, company_id: str) -> list[dict]:
    from app.modules.inventory import service as inventory

    return inventory.stock_valuation_report(session, company_id)
