"""Shipping pricing: ask each enabled carrier for a price, else use the shop's rules.

The admin chose "live rates with a rule-based fallback": a carrier configured
with `rate_source = "api"` is asked for a quote through its adapter, and when the
adapter cannot quote (not implemented yet, or the carrier is unreachable) the
shop's delivery-zone rules price the option instead — the shopper always sees a
deliverable price and the API says which source produced it.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.delivery import adapters, profiles
from app.shared.money import dec, money

SOURCE_CARRIER = "carrier"
SOURCE_RULES = "rules"
SOURCE_FALLBACK = "rules_fallback"


def _carrier_quote(carrier: dict, *, pincode: str | None, subtotal, weight_kg) -> Decimal | None:
    """Live quote from the carrier's adapter, when it can rate a parcel."""
    try:
        adapter = adapters.get_carrier_adapter(carrier["code"])
    except Exception:  # no adapter registered for this carrier yet
        return None
    rate = getattr(adapter, "rate", None)
    if rate is None:
        return None
    try:
        quote = rate(pincode=pincode, subtotal=subtotal, weight_kg=weight_kg)
    except Exception:  # a carrier outage must never break checkout
        return None
    if quote is None:
        return None
    price = quote.get("price") if isinstance(quote, dict) else quote
    return money(dec(price), 2)


def price_for(
    session: Session,
    company_id: str,
    carrier: dict,
    *,
    rule_price,
    pincode: str | None = None,
    subtotal=None,
    weight_kg=None,
) -> tuple[Decimal, str]:
    """Price one carrier option: `(amount, source)`."""
    fallback = money(dec(rule_price), 2)
    if carrier["rate_source"] == profiles.RATE_API:
        quoted = _carrier_quote(carrier, pincode=pincode, subtotal=subtotal, weight_kg=weight_kg)
        if quoted is not None:
            return quoted, SOURCE_CARRIER
        return fallback, SOURCE_FALLBACK
    return fallback, SOURCE_RULES
