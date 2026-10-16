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


_ADAPTERS: dict[str, object] = {"mock": MockGatewayAdapter()}


def get_adapter(name: str = "mock") -> object:
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Payment provider")
    return adapter
