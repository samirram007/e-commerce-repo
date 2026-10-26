"""Payment provider adapters — core domain depends on the interface only.

The default `MockGatewayAdapter` succeeds deterministically (except where the
amount is negative or the reference is empty) and generates a stable provider
reference so tests and demo flows run without real credentials. Wire a real
provider by implementing `PaymentProviderAdapter` and registering it.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import BusinessRuleError


class PaymentProviderAdapter(Protocol):
    name: str

    def charge(
        self, *, amount: Decimal, currency: str, customer_ref: str | None, idempotency_key: str
    ) -> "ProviderChargeResult": ...

    def refund(
        self, *, provider_ref: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> "ProviderChargeResult": ...


@dataclass(frozen=True)
class ProviderChargeResult:
    provider: str
    provider_ref: str
    succeeded: bool
    error_code: str | None = None
    message: str | None = None


class MockGatewayAdapter:
    """Deterministic in-process mock provider (no network, no credentials)."""

    name = "mock"

    def charge(
        self, *, amount: Decimal, currency: str, customer_ref: str | None, idempotency_key: str
    ) -> ProviderChargeResult:
        if amount <= 0:
            return ProviderChargeResult(self.name, "", False, "INVALID_AMOUNT", "Amount must be positive")
        if not idempotency_key:
            return ProviderChargeResult(self.name, "", False, "MISSING_KEY", "Idempotency key required")
        # deterministic reference derived from key + amount for test stability
        import hashlib

        digest = hashlib.sha256(f"{idempotency_key}|{amount}|{currency}".encode()).hexdigest()[:24]
        return ProviderChargeResult(self.name, f"mock_{digest}", True)

    def refund(
        self, *, provider_ref: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderChargeResult:
        if amount <= 0:
            return ProviderChargeResult(self.name, "", False, "INVALID_AMOUNT", "Amount must be positive")
        return ProviderChargeResult(self.name, f"refund_{provider_ref}", True)


class CashAdapter:
    """Cash on delivery: no external call, money is collected by the courier.

    A pending cash record is opened at checkout and settled on delivery; refunds
    are recorded as cash-out so accounting stays complete.
    """

    name = "cash"

    def charge(
        self, *, amount: Decimal, currency: str, customer_ref: str | None, idempotency_key: str
    ) -> ProviderChargeResult:
        import hashlib

        digest = hashlib.sha256(f"cash|{idempotency_key}|{amount}".encode()).hexdigest()[:16]
        return ProviderChargeResult(self.name, f"cash_{digest}", True)

    def refund(
        self, *, provider_ref: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderChargeResult:
        import hashlib

        digest = hashlib.sha256(f"cash-refund|{provider_ref}|{amount}|{idempotency_key}".encode()).hexdigest()[:16]
        return ProviderChargeResult(self.name, f"cash_refund_{digest}", True)


class RazorpayAdapter:
    """Razorpay refunds. Charges happen in Razorpay Checkout (browser), so the
    captured payment is recorded from the verified signature instead."""

    name = "razorpay"

    def charge(
        self, *, amount: Decimal, currency: str, customer_ref: str | None, idempotency_key: str
    ) -> ProviderChargeResult:
        return ProviderChargeResult(
            self.name,
            "",
            False,
            "USE_HOSTED_CHECKOUT",
            "Razorpay charges are captured by Razorpay Checkout and confirmed via signature",
        )

    def refund(
        self, *, provider_ref: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderChargeResult:
        from app.core.exceptions import AppError
        from app.modules.payments import razorpay

        try:
            result = razorpay.refund(
                provider_ref,
                amount_paise=razorpay.amount_to_paise(amount),
                notes={"idempotency_key": idempotency_key},
            )
        except AppError as exc:
            return ProviderChargeResult(self.name, "", False, exc.code, exc.message)
        return ProviderChargeResult(self.name, result.get("id", ""), True)


_ADAPTERS: dict[str, object] = {
    "mock": MockGatewayAdapter(),
    "razorpay": RazorpayAdapter(),
    "cash": CashAdapter(),
}


def get_adapter(name: str = "mock") -> object:
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Payment provider")
    return adapter
