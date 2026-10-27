"""Payment gateway control plane: which providers a company accepts, in what
order, with which credentials and which checkout customisation.

`PROVIDERS` is the single source of truth the admin panel renders from. Each
provider declares:

- `kind`      how the storefront must finish the payment (hosted modal,
              redirect to the provider, or offline/no online charge),
- `status`    `ready` when an adapter is implemented, `planned` while only the
              configuration exists (planned providers can be stored but never
              enabled, so checkout is never offered something that cannot charge),
- `credential_fields` / `settings_fields`  what the panel asks the admin for,
              including arbitrary extra key/values they may add themselves.

A company's choices live in `payment_gateways` (one row per company+provider).
Credential *values* are write-only: the API returns only the key names that are
set, and a blank value keeps whatever is stored. When a company has not stored
credentials the provider's environment configuration is used as a fallback.
"""
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.payments.models import PaymentGateway

KIND_HOSTED_MODAL = "hosted_modal"  # provider modal in the browser (Razorpay Checkout)
KIND_REDIRECT = "redirect"  # send the shopper to the provider's hosted page
KIND_OFFLINE = "offline"  # no online charge (cash on delivery)

KINDS = (KIND_HOSTED_MODAL, KIND_REDIRECT, KIND_OFFLINE)
STATUS_READY = "ready"
STATUS_PLANNED = "planned"
MODES = ("test", "live")
ANY_CURRENCY = "*"

_COD_METHOD = {"code": "cod", "label": "Cash on delivery", "provider": "cod", "kind": KIND_OFFLINE}


def _method_option(code: str, label: str) -> dict:
    return {"value": code, "label": label}


def _commerce_settings(methods: list[dict], *, extra: list[dict] | None = None) -> list[dict]:
    """Checkout customisation every online/offline gateway shares.

    `methods` is a multi-select so one gateway can serve several instruments;
    leaving it empty offers everything the provider supports.
    """
    fields = [
        {
            "key": "methods",
            "label": "Instruments offered",
            "type": "multi_select",
            "options": methods,
            "help": "Leave empty to offer everything this provider supports.",
        },
        {"key": "min_order", "label": "Minimum order value", "type": "money"},
        {"key": "max_order", "label": "Maximum order value", "type": "money"},
        {
            "key": "instructions",
            "label": "Checkout note",
            "type": "textarea",
            "help": "Shown under this method at checkout.",
        },
    ]
    return fields + (extra or [])


_CARD_METHODS = [
    _method_option("card", "Cards"),
    _method_option("netbanking", "Netbanking"),
    _method_option("wallet", "Wallets"),
]

PROVIDERS: dict[str, dict[str, Any]] = {
    "razorpay": {
        "label": "Razorpay",
        "kind": KIND_HOSTED_MODAL,
        "status": STATUS_READY,
        "currencies": ["INR"],
        "methods": ["card", "upi", "netbanking", "wallet", "emi"],
        "credential_fields": [
            {"key": "key_id", "label": "Key ID", "required": True, "placeholder": "rzp_live_…"},
            {"key": "key_secret", "label": "Key secret", "secret": True, "required": True},
            {
                "key": "webhook_secret",
                "label": "Webhook secret",
                "secret": True,
                "help": "Verifies Razorpay webhooks; falls back to RAZORPAY_WEBHOOK_SECRET.",
            },
        ],
        "settings_fields": _commerce_settings(
            [
                _method_option("card", "Cards"),
                _method_option("upi", "UPI"),
                _method_option("netbanking", "Netbanking"),
                _method_option("wallet", "Wallets"),
                _method_option("emi", "EMI"),
            ]
        ),
        "capabilities": {"hosted_checkout": True, "refunds": True, "webhooks": True},
        "docs_url": "https://razorpay.com/docs/api/",
    },
    "stripe": {
        "label": "Stripe",
        "kind": KIND_REDIRECT,
        "status": STATUS_PLANNED,
        "currencies": ["INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD", "CAD"],
        "methods": ["card", "upi", "netbanking", "wallet"],
        "credential_fields": [
            {"key": "publishable_key", "label": "Publishable key", "placeholder": "pk_live_…"},
            {"key": "secret_key", "label": "Secret key", "secret": True, "required": True, "placeholder": "sk_live_…"},
            {"key": "webhook_secret", "label": "Webhook signing secret", "secret": True, "placeholder": "whsec_…"},
        ],
        "settings_fields": _commerce_settings(
            _CARD_METHODS + [_method_option("upi", "UPI")]
        ),
        "capabilities": {"hosted_checkout": True, "refunds": True, "webhooks": True},
        "docs_url": "https://docs.stripe.com/api",
    },
    "paypal": {
        "label": "PayPal",
        "kind": KIND_REDIRECT,
        "status": STATUS_PLANNED,
        "currencies": ["USD", "EUR", "GBP", "AUD", "SGD"],
        "methods": ["card", "wallet"],
        "credential_fields": [
            {"key": "client_id", "label": "Client ID", "required": True},
            {"key": "client_secret", "label": "Client secret", "secret": True, "required": True},
            {"key": "webhook_id", "label": "Webhook ID", "help": "Verifies PayPal webhooks"},
        ],
        "settings_fields": _commerce_settings(_CARD_METHODS),
        "capabilities": {"hosted_checkout": True, "refunds": True, "webhooks": True},
        "docs_url": "https://developer.paypal.com/api/rest/",
    },
    "phonepe": {
        "label": "PhonePe",
        "kind": KIND_REDIRECT,
        "status": STATUS_PLANNED,
        "currencies": ["INR"],
        "methods": ["upi", "card", "netbanking", "wallet"],
        "credential_fields": [
            {"key": "merchant_id", "label": "Merchant ID", "required": True},
            {"key": "salt_key", "label": "Salt key", "secret": True, "required": True},
            {"key": "salt_index", "label": "Salt index", "required": True, "placeholder": "1"},
        ],
        "settings_fields": _commerce_settings(
            [
                _method_option("upi", "UPI"),
                _method_option("card", "Cards"),
                _method_option("netbanking", "Netbanking"),
                _method_option("wallet", "Wallets"),
            ]
        ),
        "capabilities": {"hosted_checkout": True, "refunds": True, "webhooks": True},
        "docs_url": "https://developer.phonepe.com/",
    },
    "paytm": {
        "label": "Paytm",
        "kind": KIND_REDIRECT,
        "status": STATUS_PLANNED,
        "currencies": ["INR"],
        "methods": ["card", "upi", "netbanking", "wallet"],
        "credential_fields": [
            {"key": "merchant_id", "label": "Merchant ID", "required": True},
            {"key": "merchant_key", "label": "Merchant key", "secret": True, "required": True},
            {"key": "website", "label": "Website code", "placeholder": "DEFAULT"},
        ],
        "settings_fields": _commerce_settings(
            [
                _method_option("upi", "UPI"),
                _method_option("card", "Cards"),
                _method_option("netbanking", "Netbanking"),
                _method_option("wallet", "Wallets"),
            ]
        ),
        "capabilities": {"hosted_checkout": True, "refunds": True, "webhooks": True},
        "docs_url": "https://business.paytm.com/docs/api/",
    },
    "cod": {
        "label": "Cash on delivery",
        "kind": KIND_OFFLINE,
        "status": STATUS_READY,
        "currencies": [ANY_CURRENCY],
        "methods": ["cod"],
        "credential_fields": [],
        "settings_fields": _commerce_settings(
            [_method_option("cod", "Cash on delivery")],
            extra=[
                {"key": "max_cash", "label": "Cash limit", "type": "money", "help": "Above this the order must be prepaid."},
                {"key": "pincode_only", "label": "Delivery PIN codes", "type": "text", "help": "Comma-separated PIN codes; empty means every deliverable PIN."},
            ],
        ),
        "capabilities": {"hosted_checkout": False, "refunds": True, "webhooks": False},
        "docs_url": "",
    },
}

# Company-scoped method codes the storefront can carry on an order: every
# provider plus the built-in sandbox instruments used when nothing is configured.
SANDBOX_METHODS = ("card", "upi")
METHOD_CODES = tuple(PROVIDERS) + SANDBOX_METHODS

_ENV_FIELDS: dict[str, dict[str, str]] = {
    "razorpay": {
        "key_id": "RAZORPAY_KEY_ID",
        "key_secret": "RAZORPAY_KEY_SECRET",
        "webhook_secret": "RAZORPAY_WEBHOOK_SECRET",
    },
}


def provider_catalog() -> list[dict]:
    """Registry metadata in declaration order (what the panel lists)."""
    return [{"code": code, **meta} for code, meta in PROVIDERS.items()]


def provider_meta(code: str) -> dict:
    meta = PROVIDERS.get(code)
    if meta is None:
        raise NotFoundError("Payment provider")
    return meta


def _decode(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def env_credentials(provider: str) -> dict:
    """Credentials from the environment, for companies that have not saved any."""
    fields = _ENV_FIELDS.get(provider)
    if not fields:
        return {}
    out = {key: (os.environ.get(env) or "").strip() for key, env in fields.items()}
    return {key: value for key, value in out.items() if value}


def _row(session: Session, company_id: str, provider: str) -> PaymentGateway | None:
    return session.scalar(
        select(PaymentGateway).where(
            PaymentGateway.company_id == company_id, PaymentGateway.provider == provider
        )
    )


def rows(session: Session, company_id: str) -> dict[str, PaymentGateway]:
    found = session.execute(
        select(PaymentGateway).where(PaymentGateway.company_id == company_id)
    ).scalars().all()
    return {row.provider: row for row in found}


def credentials_for(session: Session, company_id: str, provider: str) -> dict:
    """Stored credentials for a company, falling back to the environment.

    Merged key by key, so a company can override just the key id and keep
    whatever the deployment provides for the rest.
    """
    row = _row(session, company_id, provider)
    stored = _decode(row.credentials) if row is not None else {}
    merged = env_credentials(provider)
    merged.update({key: value for key, value in stored.items() if value})
    return merged


def _required_keys(meta: dict) -> list[str]:
    return [field["key"] for field in meta["credential_fields"] if field.get("required")]


def _configured(meta: dict, credentials: dict) -> bool:
    return all(credentials.get(key) for key in _required_keys(meta))


def overview(session: Session, company_id: str) -> list[dict]:
    """Every provider with this company's configuration (secrets never returned)."""
    stored = rows(session, company_id)
    out: list[dict] = []
    for index, (code, meta) in enumerate(PROVIDERS.items()):
        row = stored.get(code)
        credentials = credentials_for(session, company_id, code)
        source = "unset"
        if row is not None and _decode(row.credentials):
            source = "company"
        elif credentials:
            source = "environment"
        out.append(
            {
                "provider": code,
                **meta,
                "display_label": (row.label if row and row.label else meta["label"]),
                "is_enabled": bool(row.is_enabled) if row else False,
                "mode": row.mode if row else "test",
                "priority": row.priority if row else (index + 1) * 10,
                "settings": _decode(row.settings) if row else {},
                "credential_keys": sorted(key for key, value in (_decode(row.credentials) if row else {}).items() if value),
                "has_credentials": _configured(meta, credentials),
                "source": source,
                "configured": _configured(meta, credentials),
                "notes": row.notes if row else None,
            }
        )
    return out


def save(
    session: Session,
    *,
    company_id: str,
    actor_user_id: str | None,
    provider: str,
    payload: dict,
) -> PaymentGateway:
    """Create or update one company's gateway configuration.

    Blank credential values keep whatever is stored (secrets are write-only);
    settings replace the stored object, so removing a key in the panel removes
    it here. Enabling a gateway validates its required credentials and refuses
    providers whose adapter is not implemented yet.
    """
    meta = provider_meta(provider)
    row = _row(session, company_id, provider)
    if row is None:
        row = PaymentGateway(
            company_id=company_id, provider=provider, credentials="{}", settings="{}", created_by=actor_user_id
        )
        session.add(row)

    allowed = {field["key"] for field in meta["credential_fields"]}
    credentials = _decode(row.credentials)
    for key, value in (payload.get("credentials") or {}).items():
        if key not in allowed:
            raise BusinessRuleError("UNKNOWN_CREDENTIAL", f"'{key}' is not a {meta['label']} credential")
        text = (str(value) if value is not None else "").strip()
        if text:
            credentials[key] = text
    row.credentials = json.dumps(credentials)

    if payload.get("settings") is not None:
        row.settings = json.dumps(_clean_settings(meta, payload["settings"]))

    if payload.get("label") is not None:
        row.label = (payload["label"] or "").strip() or None
    if payload.get("mode") is not None:
        if payload["mode"] not in MODES:
            raise BusinessRuleError("BAD_GATEWAY_MODE", f"Mode must be one of {', '.join(MODES)}")
        row.mode = payload["mode"]
    if payload.get("priority") is not None:
        row.priority = int(payload["priority"])
    if payload.get("notes") is not None:
        row.notes = payload["notes"] or None
    if payload.get("is_enabled") is not None:
        enable = bool(payload["is_enabled"])
        if enable and meta["status"] != STATUS_READY:
            raise BusinessRuleError(
                "GATEWAY_NOT_AVAILABLE",
                f"{meta['label']} cannot be enabled yet — its checkout adapter has not shipped",
            )
        if enable and meta["kind"] != KIND_OFFLINE and not _configured(meta, credentials):
            missing = ", ".join(k for k in _required_keys(meta) if not credentials.get(k))
            raise BusinessRuleError(
                "GATEWAY_NOT_CONFIGURED",
                f"Add the {meta['label']} credentials before enabling it (missing: {missing})",
            )
        row.is_enabled = enable
    session.flush()
    return row


def _clean_settings(meta: dict, settings: dict) -> dict:
    """Validate the admin's checkout customisation, key by key.

    Known fields are validated (instrument codes must belong to the provider,
    money fields must parse); any additional key the admin adds is stored as
    sent, so the panel can carry provider-specific extras without code changes.
    """
    from app.shared.money import dec, money

    known = {field["key"] for field in meta["settings_fields"]}
    out: dict[str, Any] = {}
    for key, value in settings.items():
        if value is None or value == "" or value == []:
            continue
        if key == "methods":
            if not isinstance(value, list):
                raise BusinessRuleError("BAD_GATEWAY_SETTINGS", "Instruments must be a list")
            unknown = [code for code in value if code not in meta["methods"]]
            if unknown:
                raise BusinessRuleError(
                    "BAD_GATEWAY_SETTINGS",
                    f"{meta['label']} does not support: {', '.join(unknown)}",
                )
            out[key] = list(value)
            continue
        if key in known and str(meta_field_type(meta, key)) == "money":
            out[key] = str(money(dec(value), 2))
            continue
        out[key] = value
    return out


def meta_field_type(meta: dict, key: str) -> str | None:
    for field in meta["settings_fields"]:
        if field["key"] == key:
            return field.get("type") or "text"
    return None


def remove(session: Session, company_id: str, provider: str) -> None:
    row = _row(session, company_id, provider)
    if row is None:
        raise NotFoundError("Payment gateway")
    session.delete(row)
    session.flush()


def checkout_gateways(session: Session, company_id: str) -> list[dict]:
    """Enabled gateways the storefront may offer, in the admin's display order.

    A gateway that needs credentials is skipped when they are missing, and
    gateways whose adapter has not shipped yet are never offered, so the
    storefront can only show methods that can actually take the payment.
    """
    stored = rows(session, company_id)
    out: list[dict] = []
    for code, meta in PROVIDERS.items():
        row = stored.get(code)
        if row is None or not row.is_enabled or meta["status"] != STATUS_READY:
            continue
        credentials = credentials_for(session, company_id, code)
        if meta["kind"] != KIND_OFFLINE and not _configured(meta, credentials):
            continue
        settings = _decode(row.settings)
        out.append(
            {
                "code": code,
                "provider": code,
                "label": (row.label or meta["label"]),
                "kind": meta["kind"],
                "mode": row.mode,
                "methods": settings.get("methods") or list(meta["methods"]),
                "instructions": settings.get("instructions"),
                "min_order": settings.get("min_order"),
                "max_order": settings.get("max_order"),
                "settings": settings,
                "priority": row.priority,
            }
        )
    out.sort(key=lambda gateway: (gateway["priority"], gateway["label"]))
    return out


def gateway_for(session: Session, company_id: str, code: str) -> dict | None:
    """One enabled gateway, for validating the method a shopper chose."""
    for gateway in checkout_gateways(session, company_id):
        if gateway["code"] == code:
            return gateway
    return None


def cod_gateway(session: Session, company_id: str) -> dict | None:
    return gateway_for(session, company_id, "cod")
