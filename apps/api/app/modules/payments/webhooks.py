"""Provider webhooks: signature verification is the only authentication.

Razorpay and Stripe POST to
``{PUBLIC_API_BASE_URL}/api/v1/payments/webhooks/{provider}/{company_id}`` —
provider servers cannot carry a bearer token or an ``X-Company-Id`` header, so
the raw body is verified against the stored webhook secret (HMAC-SHA256) before
anything is trusted.

Delivery is at-least-once and out-of-order, so:

* the event is applied inside ``run_idempotent`` keyed by the provider's
  event id — a redelivery replays;
* ``payment.succeeded`` finalizes the order through the same
  ``pay:{order_id}`` key the browser callback uses, so whichever arrives first
  wins exactly once (one payment row, one invoice, one journal);
* ``payment.failed`` only marks the pending receipt failed — the order stays
  ``pending_payment`` so the shopper can retry.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, BusinessRuleError, NotFoundError
from app.modules.payments.adapters import PaymentProviderAdapter, get_adapter
from app.modules.payments.gateways import MOCK_CREDS, credentials_for
from app.modules.payments.models import PaymentGatewayConfig, PaymentRecord
from app.shared.idempotency import run_idempotent

logger = logging.getLogger("erp")

#: Signature-level failures worth retrying the other mode for; anything else is
#: terminal for this delivery.
_SIGNATURE_ERRORS = {
    "WEBHOOK_BAD_SIGNATURE",
    "WEBHOOK_STALE",
    "WEBHOOK_NOT_CONFIGURED",
    "SECRET_DECRYPT_FAILED",
    "KEY_MODE_MISMATCH",
}


def _candidate_modes(config: PaymentGatewayConfig, record: PaymentRecord | None) -> list[str]:
    """Mode of the matching payment first (if we could guess it), then the
    config's active mode, then the other one."""
    ordered: list[str] = []
    for mode in ([record.mode] if record and record.mode else []) + [config.mode]:
        if mode and mode not in ordered:
            ordered.append(mode)
    for mode in ("test", "live"):
        if mode not in ordered:
            ordered.append(mode)
    return ordered


def _intent_guess(raw_body: bytes) -> str | None:
    """Best-effort intent id from an unverified body, used only to order which
    mode's secret we try first — never to decide whether to trust the event."""
    try:
        body = json.loads(raw_body or b"{}")
    except (ValueError, TypeError):
        return None
    payload = body.get("payload") or {}
    payment = (payload.get("payment") or {}).get("entity") or {}
    if payment.get("order_id"):
        return str(payment["order_id"])
    obj = (body.get("data") or {}).get("object") or {}
    if obj.get("id"):
        return str(obj["id"])
    if body.get("intent_id"):
        return str(body["intent_id"])
    return None


def _find_record(
    session: Session, company_id: str, provider: str, intent_id: str | None, charge_id: str | None
) -> PaymentRecord | None:
    if intent_id:
        row = session.scalar(
            select(PaymentRecord).where(
                PaymentRecord.company_id == company_id,
                PaymentRecord.provider == provider,
                PaymentRecord.provider_ref == intent_id,
            )
        )
        if row is not None:
            return row
    if charge_id:
        return session.scalar(
            select(PaymentRecord).where(
                PaymentRecord.company_id == company_id,
                PaymentRecord.provider == provider,
                PaymentRecord.charge_ref == charge_id,
            )
        )
    return None


def handle_webhook(
    session: Session, *, provider: str, company_id: str, raw_body: bytes, headers: dict
) -> dict:
    config = session.scalar(
        select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.company_id == company_id,
            PaymentGatewayConfig.provider == provider,
        )
    )
    try:
        adapter: PaymentProviderAdapter = get_adapter(provider)
    except NotFoundError:
        raise BusinessRuleError("UNKNOWN_PROVIDER", f"Unknown payment provider '{provider}'") from None

    if config is None:
        if provider != "mock":
            raise NotFoundError("Payment gateway")
        adapter, creds = adapter, MOCK_CREDS
        record = _find_record(session, company_id, provider, _intent_guess(raw_body), None)
    else:
        record = _find_record(session, company_id, provider, _intent_guess(raw_body), None)
        creds = None
        last_error: AppError | None = None
        for mode in _candidate_modes(config, record):
            try:
                candidate = credentials_for(config, mode)
                if not candidate.webhook_secret:
                    continue
                event = adapter.parse_webhook(candidate, raw_body=raw_body, headers=headers)
                creds = candidate
                break
            except AppError as exc:
                if exc.code == "WEBHOOK_UNSUPPORTED_EVENT":
                    # Acknowledge events we don't act on so the provider stops retrying.
                    return {"received": True, "ignored": exc.message}
                if exc.code in _SIGNATURE_ERRORS:
                    last_error = exc
                    continue
                raise
        if creds is None:
            raise last_error or BusinessRuleError(
                "WEBHOOK_NOT_CONFIGURED", "No webhook secret configured for this provider"
            )

    if config is None:
        try:
            event = adapter.parse_webhook(creds, raw_body=raw_body, headers=headers)
        except AppError as exc:
            if exc.code == "WEBHOOK_UNSUPPORTED_EVENT":
                return {"received": True, "ignored": exc.message}
            raise

    def _apply() -> dict:
        return _apply_event(session, provider=provider, company_id=company_id, event=event)

    result, replayed = run_idempotent(
        session,
        scope=f"webhook:{company_id}",
        key=f"{provider}:{event.event_id}",
        company_id=company_id,
        execute=_apply,
    )
    return {**result, "replayed": replayed}


def _apply_event(session: Session, *, provider: str, company_id: str, event) -> dict:
    from app.modules.sales import service as sales_svc

    record = _find_record(session, company_id, provider, event.intent_id, event.provider_ref)
    if record is None:
        # Event for another order/company, or the intent was never created here.
        logger.info(
            "payment_webhook_unmatched provider=%s company=%s type=%s", provider, company_id, event.type
        )
        return {"received": True, "matched": False, "type": event.type}

    if event.type == "payment.succeeded":
        if record.status != "succeeded":
            sales_svc.confirm_order_payment(
                session,
                company_id=company_id,
                actor_user_id=None,
                order_id=record.order_id,
                payment=record,
                charge_ref=event.provider_ref,
            )
        return {"received": True, "matched": True, "type": event.type, "payment_id": record.id}

    if event.type == "payment.failed":
        sales_svc.fail_order_payment(session, record, message="Provider reported a failed payment")
        return {"received": True, "matched": True, "type": event.type, "payment_id": record.id}

    # refund.succeeded: refunds are booked by the admin/returns flow; the
    # notification only confirms the provider side.
    return {"received": True, "matched": True, "type": event.type, "payment_id": record.id}