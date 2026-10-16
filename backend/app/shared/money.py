"""Shared arithmetic helpers for money and quantities — no floats for money."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_QUANT_HUNDREDTH = Decimal("0.01")
_QUANT_FOURTH = Decimal("0.0001")


def dec(value) -> Decimal:
    """Parse a numeric-ish value into Decimal; raise on garbage."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise InvalidOperation("bool is not a number")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value.strip())
    raise InvalidOperation(f"cannot parse {type(value).__name__} as Decimal")


def money(value, exponent: int | None = 2) -> Decimal:
    """Quantize a monetary amount using HALF_UP, defaulting to cents."""
    places = _QUANT_HUNDREDTH if exponent in (2, None) else Decimal(1).scaleb(-exponent)
    return dec(value).quantize(places, rounding=ROUND_HALF_UP)


def qty(value) -> Decimal:
    """Quantize a quantity to 4 dp (covers unit conversions)."""
    return dec(value).quantize(_QUANT_FOURTH, rounding=ROUND_HALF_UP)


def rate(value) -> Decimal:
    """Quantize an exchange rate to 6 significant decimals."""
    return dec(value).quantize(_QUANT_HUNDREDTH / Decimal(10_000))


def is_zero(value) -> bool:
    return dec(value) == 0


def to_decimal_str(value: Decimal) -> str:
    """Stable string form for JSON transport of money values."""
    return format(value, "f")
