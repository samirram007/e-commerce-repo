"""Admin payment-gateway configuration API.

    GET    /payments/gateways                      — all providers (masked)
    PUT    /payments/gateways/{provider}           — upsert keys/methods/priority
    POST   /payments/gateways/{provider}/mode      — switch test ⇄ live
    POST   /payments/gateways/{provider}/test      — live connection check

Guarded by ``P_PAYMENTS_MANAGE``. Secrets are **write-only**: responses only
ever carry presence flags plus a masked last-4 hint, and every change is
audit-logged without any secret material.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import P_PAYMENTS_MANAGE
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.payments.adapters import get_adapter, validate_key_mode
from app.modules.payments.gateways import credentials_for
from app.modules.payments.models import GATEWAY_MODES, GATEWAY_PROVIDERS, PaymentGatewayConfig
from app.shared.crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/payments/gateways")

#: Defaults for a provider that has never been configured (disabled placeholder).
_DEFAULT_METHODS = ["card", "upi"]
_DEFAULT_PRIORITY = {"razorpay": 10, "stripe": 10, "mock": 100}
_DISPLAY_NAMES = {"razorpay": "Razorpay", "stripe": "Stripe", "mock": "Mock (dev/test)"}


class GatewayIn(BaseModel):
    is_enabled: bool = False
    display_name: str | None = Field(default=None, max_length=80)
    mode: str | None = None
    supported_methods: list[str] = Field(default_factory=lambda: list(_DEFAULT_METHODS))
    priority: int = Field(default=10, ge=0, le=1000)
    test_public_key: str | None = None
    test_secret: str | None = None  # omitted/"" → keep, explicit null → clear
    test_webhook_secret: str | None = None
    live_public_key: str | None = None
    live_secret: str | None = None
    live_webhook_secret: str | None = None


class ModeIn(BaseModel):
    mode: str


class ModeKeysOut(BaseModel):
    public_key: str | None = None
    has_secret: bool = False
    secret_hint: str | None = None
    has_webhook_secret: bool = False
    webhook_secret_hint: str | None = None


class GatewayOut(BaseModel):
    provider: str
    display_name: str
    is_enabled: bool
    mode: str
    supported_methods: list[str]
    priority: int
    configured: bool
    test: ModeKeysOut
    live: ModeKeysOut
    webhook_url: str
    updated_at: str | None = None


def _hint(encrypted: str | None) -> str | None:
    """Masked last-4 of the decrypted secret — never the secret itself."""
    if not encrypted:
        return None
    try:
        value = decrypt_secret(encrypted)
    except BusinessRuleError:
        return None
    return value[-4:] if len(value) >= 4 else value


def _mode_keys(config: PaymentGatewayConfig | None, mode: str) -> ModeKeysOut:
    is_test = mode == "test"
    if config is None:
        return ModeKeysOut()
    secret = config.test_secret_encrypted if is_test else config.live_secret_encrypted
    webhook = (
        config.test_webhook_secret_encrypted if is_test else config.live_webhook_secret_encrypted
    )
    return ModeKeysOut(
        public_key=(config.test_public_key if is_test else config.live_public_key),
        has_secret=bool(secret),
        secret_hint=_hint(secret),
        has_webhook_secret=bool(webhook),
        webhook_secret_hint=_hint(webhook),
    )


def webhook_url(provider: str, company_id: str) -> str:
    base = get_settings().public_api_base_url.rstrip("/")
    return f"{base}/api/v1/payments/webhooks/{provider}/{company_id}"


def _out(config: PaymentGatewayConfig | None, provider: str, company_id: str) -> GatewayOut:
    if config is None:
        return GatewayOut(
            provider=provider,
            display_name=_DISPLAY_NAMES.get(provider, provider.title()),
            is_enabled=False,
            mode="test",
            supported_methods=list(_DEFAULT_METHODS),
            priority=_DEFAULT_PRIORITY.get(provider, 10),
            configured=False,
            test=ModeKeysOut(),
            live=ModeKeysOut(),
            webhook_url=webhook_url(provider, company_id),
            updated_at=None,
        )
    return GatewayOut(
        provider=config.provider,
        display_name=config.display_name or _DISPLAY_NAMES.get(provider, provider.title()),
        is_enabled=config.is_enabled,
        mode=config.mode,
        supported_methods=list(config.supported_methods or []),
        priority=config.priority,
        configured=bool(config.test_secret_encrypted or config.live_secret_encrypted),
        test=_mode_keys(config, "test"),
        live=_mode_keys(config, "live"),
        webhook_url=webhook_url(provider, company_id),
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


def _get_or_none(session: Session, company_id: str, provider: str) -> PaymentGatewayConfig | None:
    return session.scalar(
        select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.company_id == company_id,
            PaymentGatewayConfig.provider == provider,
        )
    )


def _check_provider(provider: str) -> str:
    if provider not in GATEWAY_PROVIDERS:
        raise BusinessRuleError(
            "UNKNOWN_PROVIDER",
            f"Unknown provider '{provider}' (expected one of {GATEWAY_PROVIDERS})",
        )
    return provider


def _audit(session: Session, ctx: CompanyCtx, config: PaymentGatewayConfig, action: str) -> None:
    log_action(
        session,
        action=action,
        entity_type="payment_gateway_config",
        entity_id=config.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={
            "provider": config.provider,
            "is_enabled": config.is_enabled,
            "mode": config.mode,
            "supported_methods": list(config.supported_methods or []),
            "priority": config.priority,
        },
    )


def _validate_effective_keys(config: PaymentGatewayConfig) -> None:
    """Key prefixes must match their mode on save (and again at use time)."""
    for mode in GATEWAY_MODES:
        is_test = mode == "test"
        public = config.test_public_key if is_test else config.live_public_key
        encrypted = config.test_secret_encrypted if is_test else config.live_secret_encrypted
        secret = decrypt_secret(encrypted) if encrypted else None
        validate_key_mode(config.provider, mode, public, secret)


@router.get("", response_model=list[GatewayOut])
def list_gateways(
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    rows = session.execute(
        select(PaymentGatewayConfig).where(PaymentGatewayConfig.company_id == ctx.company_id)
    ).scalars().all()
    by_provider = {row.provider: row for row in rows}
    return [
        _out(by_provider.get(provider), provider, ctx.company_id)
        for provider in GATEWAY_PROVIDERS
    ]


@router.put("/{provider}", response_model=GatewayOut)
def upsert_gateway(
    provider: str,
    payload: GatewayIn,
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    _check_provider(provider)
    config = _get_or_none(session, ctx.company_id, provider)
    if config is None:
        config = PaymentGatewayConfig(
            company_id=ctx.company_id,
            provider=provider,
            is_enabled=False,
            mode="test",
            supported_methods=list(_DEFAULT_METHODS),
            priority=_DEFAULT_PRIORITY.get(provider, 10),
            created_by=ctx.user.id,
        )
        session.add(config)

    data = payload.model_dump(exclude_unset=True)

    def _apply_text(field_name: str, value) -> None:
        """Omitted/empty keeps the stored value; explicit null clears it."""
        if value is None:
            setattr(config, field_name, None)
        elif value == "":
            return
        else:
            setattr(config, field_name, value.strip())

    def _apply_secret(encrypted_field: str, value) -> None:
        if value is None:
            setattr(config, encrypted_field, None)
        elif value == "":
            return
        else:
            setattr(config, encrypted_field, encrypt_secret(value))

    if "is_enabled" in data:
        config.is_enabled = bool(data["is_enabled"])
    if "display_name" in data:
        config.display_name = (data["display_name"] or None)
    if "supported_methods" in data:
        config.supported_methods = list(data["supported_methods"] or [])
    if "priority" in data:
        config.priority = int(data["priority"])
    if "mode" in data and data["mode"] is not None:
        config.mode = _mode_value(data["mode"])

    if "test_public_key" in data:
        _apply_text("test_public_key", data["test_public_key"])
    if "live_public_key" in data:
        _apply_text("live_public_key", data["live_public_key"])
    if "test_secret" in data:
        _apply_secret("test_secret_encrypted", data["test_secret"])
    if "live_secret" in data:
        _apply_secret("live_secret_encrypted", data["live_secret"])
    if "test_webhook_secret" in data:
        _apply_secret("test_webhook_secret_encrypted", data["test_webhook_secret"])
    if "live_webhook_secret" in data:
        _apply_secret("live_webhook_secret_encrypted", data["live_webhook_secret"])

    _validate_effective_keys(config)
    if config.mode == "live" and not (
        config.live_public_key and config.live_secret_encrypted
    ):
        raise BusinessRuleError(
            "LIVE_KEYS_REQUIRED", "Enter the live keys before switching this provider to live"
        )
    session.flush()
    _audit(session, ctx, config, "payment_gateway.updated")
    return _out(config, provider, ctx.company_id)


def _mode_value(mode: str) -> str:
    mode = (mode or "").strip().lower()
    if mode not in GATEWAY_MODES:
        raise BusinessRuleError("BAD_MODE", f"mode must be one of {GATEWAY_MODES}")
    return mode


@router.post("/{provider}/mode", response_model=GatewayOut)
def switch_mode(
    provider: str,
    payload: ModeIn,
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    _check_provider(provider)
    mode = _mode_value(payload.mode)
    config = _get_or_none(session, ctx.company_id, provider)
    if config is None:
        raise NotFoundError("Payment gateway")
    if mode == "live" and not (config.live_public_key and config.live_secret_encrypted):
        raise BusinessRuleError(
            "LIVE_KEYS_REQUIRED", "Enter the live keys before switching this provider to live"
        )
    _validate_effective_keys(config)
    config.mode = mode
    session.flush()
    _audit(session, ctx, config, "payment_gateway.mode_changed")
    return _out(config, provider, ctx.company_id)


@router.post("/{provider}/test")
def test_gateway(
    provider: str,
    ctx: CompanyCtx = Depends(guard(P_PAYMENTS_MANAGE)),
    session: Session = Depends(get_db),
):
    _check_provider(provider)
    config = _get_or_none(session, ctx.company_id, provider)
    if config is None:
        if provider == "mock":
            return {"ok": True, "message": "Mock gateway is always available", "mode": "test"}
        raise NotFoundError("Payment gateway")
    creds = credentials_for(config, config.mode)
    if provider != "mock" and not creds.secret_key:
        raise BusinessRuleError(
            "NO_KEYS", f"No {config.mode} secret key saved for {provider} yet"
        )
    ok, message = get_adapter(provider).test_connection(creds)
    return {"ok": ok, "message": message, "mode": config.mode}