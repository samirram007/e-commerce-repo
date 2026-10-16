"""Carrier adapters — fulfillment module depends on this interface only.

The mock carrier issues deterministic tracking numbers and (for the mock rule)
completes delivery immediately after dispatch so tests cover the full state
machine without real networks. Real carriers plug in by implementing
`CarrierAdapter` and registering in `_ADAPTERS`. Delivery truth always comes
from the carrier webhook — dispatch alone never marks an order delivered.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DispatchResult:
    provider: str
    tracking_number: str


CarrierDispatchResult = DispatchResult


class CarrierAdapter(Protocol):
    name: str

    def dispatch(
        self, *, shipment_ref: str, address: str, weight_hint: str | None = None
    ) -> DispatchResult: ...


class MockCarrierAdapter:
    name = "mock"

    def dispatch(
        self, *, shipment_ref: str, address: str, weight_hint: str | None = None
    ) -> DispatchResult:
        import hashlib

        digest = hashlib.sha256(shipment_ref.encode()).hexdigest()[:16].upper()
        return DispatchResult(provider=self.name, tracking_number=f"MOCK{digest}")


_ADAPTERS: dict[str, CarrierAdapter] = {"mock": MockCarrierAdapter()}


def get_carrier_adapter(name: str = "mock") -> CarrierAdapter:
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Carrier adapter")
    return adapter


def available_carriers() -> list[str]:
    return list(_ADAPTERS.keys())
