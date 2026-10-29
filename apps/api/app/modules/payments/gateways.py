"""Gateway resolution: turn (company, method) into (adapter, creds, config).

Resolution rules:

* Only **enabled** configs whose ``supported_methods`` contain the requested
  method compete; the lowest ``priority`` wins.
* Secrets are decrypted for the config's **current mode** and re-validated
  against that mode's key prefix, so a mode switch takes effect on the next
  request with no restart.
* With no usable config the company falls back to the offline ``mock``
  gateway outside production; in production a missing gateway is an error
  (``NO_PAYMENT_GATEWAY``) rather than a silent free pass.

Refunds and webhooks resolve by provider (and by the mode stored on the
original ``PaymentRecord``), so switching modes never rewrites history.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.payments.adapters import (
    GatewayCredentials,
    PaymentProviderAdapter,
    get_adapter,
    validate_key_mode,
)
from app.modules.payments.models import PaymentGatewayConfig
from app.shared.crypto import decrypt_secret

#: Credentials for the offline mock provider (never encrypted, never sent).
MOCK_CREDS = GatewayCredentials(mode="test", public_key="", secret_key="", webhook_secret=None)

MODES = ("test", "live")


def credentials_for(config: PaymentGatewayConfig, mode: str) -> GatewayCredentials:
    """Decrypt the stored secrets for one mode and sanity-check the prefixes."""
    if mode not in MODES:
        raise BusinessRuleError("BAD_MODE", f"mode must be one of {list(MODES)}")
    is_test = mode == "test"
    public_key = (config.test_public_key if is_test else config.live_public_key) or ""
    secret_enc = config.test_secret_encrypted if is_test else config.live_secret_encrypted
    webhook_enc = (
        config.test_webhook_secret_encrypted if is_test else config.live_webhook_secret_encrypted
    )
    secret = decrypt_secret(secret_enc) if secret_enc else ""
    webhook_secret = decrypt_secret(webhook_enc) if webhook_enc else None
    validate_key_mode(config.provider, mode, public_key, secret)
    return GatewayCredentials(
        mode=mode, public_key=public_key, secret_key=secret, webhook_secret=webhook_secret
    )


def _registered(config: PaymentGatewayConfig) -> bool:
    from app.modules.payments.adapters import ADAPTERS

    return config.provider in ADAPTERS


def resolve_gateway(
    session: Session, company_id: str, method: str
) -> tuple[PaymentProviderAdapter, GatewayCredentials | None, PaymentGatewayConfig | None]:
    """Pick the gateway that should serve a storefront payment method."""
    rows = session.execute(
        select(PaymentGatewayConfig).where(PaymentGatewayConfig.company_id == company_id)
    ).scalars().all()
    candidates = [
        row
        for row in rows
        if row.is_enabled and _registered(row) and method in (row.supported_methods or [])
    ]
    candidates.sort(key=lambda row: (row.priority, row.created_at, row.provider))
    if candidates:
        config = candidates[0]
        return get_adapter(config.provider), credentials_for(config, config.mode), config

    settings = get_settings()
    if settings.is_prod:
        raise BusinessRuleError(
            "NO_PAYMENT_GATEWAY",
            f"No enabled payment gateway handles '{method}' — configure one in "
            "Settings → Payment gateways",
        )
    # Dev/test convenience: keep checkout working before any keys are entered.
    return get_adapter("mock"), MOCK_CREDS, None


def get_gateway_by_name(
    session: Session, company_id: str, provider: str, mode: str | None = None
) -> tuple[PaymentProviderAdapter, GatewayCredentials | None, PaymentGatewayConfig | None]:
    """Resolve a specific provider (webhooks, refunds).

    `mode` defaults to the config's current mode; refunds pass the mode stored
    on the original payment so a later mode switch cannot break them.
    """
    config = session.scalar(
        select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.company_id == company_id,
            PaymentGatewayConfig.provider == provider,
        )
    )
    if config is None:
        if provider == "mock":
            return get_adapter("mock"), MOCK_CREDS, None
        raise NotFoundError("Payment gateway")
    return (
        get_adapter(provider),
        credentials_for(config, mode or config.mode),
        config,
    )


def enabled_configs(session: Session, company_id: str) -> list[PaymentGatewayConfig]:
    return list(
        session.execute(
            select(PaymentGatewayConfig)
            .where(PaymentGatewayConfig.company_id == company_id)
            .order_by(PaymentGatewayConfig.provider)
        ).scalars()
    )