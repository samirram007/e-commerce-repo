"""Third-party shipping: the carrier catalog and each company's configuration.

`CARRIERS` is the single source of truth the admin panel renders from — each
carrier declares the credential fields the panel asks for and whether its
dispatch/rate adapter has shipped (`status`). A carrier whose adapter is missing
can still be configured (credentials are stored), but it cannot be enabled, so a
shop never promises a carrier it cannot book.

Rate quoting lives in `rates.py`: enabled carriers are asked for a price, and the
storefront falls back to the shop's own delivery-zone rules when none answers.
"""
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.delivery.models import CarrierProfile

# How a carrier moves a parcel: `manual` is the merchant's own delivery,
# `api` is a third-party carrier booked through its API.
KIND_MANUAL = "manual"
KIND_API = "api"

STATUS_READY = "ready"
STATUS_PLANNED = "planned"

# Where a price comes from: the carrier's rate API, or the shop's zone rules.
RATE_API = "api"
RATE_RULES = "rules"

#: Credentials the deployment can supply for every company (env fallbacks).
_ENV_PREFIX = "SHIPPING_"


def _fields(*specs: tuple[str, str, bool]) -> list[dict]:
    """Credential field specs: (key, label, secret)."""
    return [
        {"key": key, "label": label, "secret": secret, "required": index == 0 or not secret}
        for index, (key, label, secret) in enumerate(specs)
    ]


def _api_carrier(label: str, docs_url: str, fields: list[dict]) -> dict:
    return {
        "label": label,
        "kind": KIND_API,
        "status": STATUS_PLANNED,  # configurable now; dispatch/rate adapter pending
        "rate_source": RATE_API,
        "credential_fields": fields,
        "docs_url": docs_url,
    }


CARRIERS: dict[str, dict[str, Any]] = {
    "manual": {
        "label": "Own delivery",
        "kind": KIND_MANUAL,
        "status": STATUS_READY,
        "rate_source": RATE_RULES,
        "credential_fields": [],
        "docs_url": "",
    },
    "shiprocket": _api_carrier(
        "Shiprocket",
        "https://apidocs.shiprocket.in/",
        _fields(
            ("email", "API email", False),
            ("password", "API password", True),
        ),
    ),
    "delhivery": _api_carrier(
        "Delhivery",
        "https://delhivery-express.readme.io/",
        _fields(("api_token", "API token", True), ("client_name", "Client name", False)),
    ),
    "bluedart": _api_carrier(
        "BlueDart",
        "https://www.bluedart.com/web/guest/api-integration",
        _fields(
            ("login_id", "Login ID", False),
            ("license_key", "Licence key", True),
            ("customer_code", "Customer code", False),
        ),
    ),
    "dtdc": _api_carrier(
        "DTDC",
        "https://www.dtdc.in/api-integration.asp",
        _fields(("api_key", "API key", True), ("customer_code", "Customer code", False)),
    ),
    "fedex": _api_carrier(
        "FedEx",
        "https://developer.fedex.com/api/en-us/home.html",
        _fields(
            ("client_id", "Client ID", False),
            ("client_secret", "Client secret", True),
            ("account_number", "Account number", False),
        ),
    ),
    "dhl": _api_carrier(
        "DHL Express",
        "https://developer.dhl.com/",
        _fields(
            ("api_key", "API key", True),
            ("api_secret", "API secret", True),
            ("account_number", "Account number", False),
        ),
    ),
    "custom": _api_carrier(
        "Custom carrier (own API)",
        "",
        _fields(("api_base", "API base URL", False), ("api_key", "API key", True)),
    ),
}


def carrier_catalog() -> list[dict]:
    return [{"code": code, **meta} for code, meta in CARRIERS.items()]


def carrier_meta(code: str) -> dict:
    meta = CARRIERS.get(code)
    if meta is None:
        raise NotFoundError("Shipping carrier")
    return meta


def _decode(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def env_credentials(carrier: str) -> dict:
    """`SHIPPING_<CARRIER>_<FIELD>` environment fallbacks, when set."""
    out: dict[str, str] = {}
    for field in CARRIERS.get(carrier, {}).get("credential_fields", []):
        value = (os.environ.get(f"{_ENV_PREFIX}{carrier.upper()}_{field['key'].upper()}") or "").strip()
        if value:
            out[field["key"]] = value
    return out


def _row(session: Session, company_id: str, carrier: str) -> CarrierProfile | None:
    return session.scalar(
        select(CarrierProfile).where(
            CarrierProfile.company_id == company_id, CarrierProfile.carrier == carrier
        )
    )


def rows(session: Session, company_id: str) -> dict[str, CarrierProfile]:
    found = session.execute(
        select(CarrierProfile).where(CarrierProfile.company_id == company_id)
    ).scalars().all()
    return {row.carrier: row for row in found}


def credentials_for(session: Session, company_id: str, carrier: str) -> dict:
    """Stored credentials for a company, key by key over the environment."""
    row = _row(session, company_id, carrier)
    stored = _decode(row.credentials) if row is not None else {}
    merged = env_credentials(carrier)
    merged.update({key: value for key, value in stored.items() if value})
    return merged


def _required_keys(meta: dict) -> list[str]:
    return [field["key"] for field in meta["credential_fields"] if field.get("required")]


def _configured(meta: dict, credentials: dict) -> bool:
    return all(credentials.get(key) for key in _required_keys(meta))


def overview(session: Session, company_id: str) -> list[dict]:
    """Every carrier with this company's configuration (secrets never returned)."""
    stored = rows(session, company_id)
    out: list[dict] = []
    for index, (code, meta) in enumerate(CARRIERS.items()):
        row = stored.get(code)
        credentials = credentials_for(session, company_id, code)
        source = "unset"
        if row is not None and _decode(row.credentials):
            source = "company"
        elif credentials:
            source = "environment"
        out.append(
            {
                "carrier": code,
                **meta,
                "display_label": (row.label if row and row.label else meta["label"]),
                "is_enabled": bool(row.is_enabled) if row else False,
                "priority": row.priority if row else (index + 1) * 10,
                "settings": _decode(row.settings) if row else {},
                "credential_keys": sorted(
                    key for key, value in (_decode(row.credentials) if row else {}).items() if value
                ),
                "has_credentials": _configured(meta, credentials),
                "configured": _configured(meta, credentials),
                "source": source,
                "notes": row.notes if row else None,
            }
        )
    return out


def save(
    session: Session,
    *,
    company_id: str,
    actor_user_id: str | None,
    carrier: str,
    payload: dict,
) -> CarrierProfile:
    """Create or update one company's carrier configuration.

    Blank credential values keep what is stored. Enabling validates the required
    credentials and refuses carriers whose adapter has not shipped.
    """
    meta = carrier_meta(carrier)
    row = _row(session, company_id, carrier)
    if row is None:
        row = CarrierProfile(
            company_id=company_id, carrier=carrier, credentials="{}", settings="{}", created_by=actor_user_id
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
        row.settings = json.dumps({key: value for key, value in payload["settings"].items() if value not in (None, "")})
    if payload.get("label") is not None:
        row.label = (payload["label"] or "").strip() or None
    if payload.get("priority") is not None:
        row.priority = int(payload["priority"])
    if payload.get("notes") is not None:
        row.notes = payload["notes"] or None
    if payload.get("is_enabled") is not None:
        enable = bool(payload["is_enabled"])
        if enable and meta["status"] != STATUS_READY:
            raise BusinessRuleError(
                "CARRIER_NOT_AVAILABLE",
                f"{meta['label']} cannot be enabled yet — its dispatch and rate adapter has not shipped",
            )
        if enable and not _configured(meta, credentials):
            missing = ", ".join(key for key in _required_keys(meta) if not credentials.get(key))
            raise BusinessRuleError(
                "CARRIER_NOT_CONFIGURED",
                f"Add the {meta['label']} credentials before enabling it (missing: {missing})",
            )
        row.is_enabled = enable
    session.flush()
    return row


def remove(session: Session, company_id: str, carrier: str) -> None:
    row = _row(session, company_id, carrier)
    if row is None:
        raise NotFoundError("Shipping carrier")
    session.delete(row)
    session.flush()


def enabled_carriers(session: Session, company_id: str) -> list[dict]:
    """Carriers the shop may offer, in the admin's display order.

    A carrier that needs credentials is skipped while they are missing, and
    carriers whose adapter has not shipped are never offered, so checkout can
    only show carriers that can actually take the parcel.
    """
    stored = rows(session, company_id)
    out: list[dict] = []
    for code, meta in CARRIERS.items():
        row = stored.get(code)
        if row is None or not row.is_enabled or meta["status"] != STATUS_READY:
            continue
        credentials = credentials_for(session, company_id, code)
        if not _configured(meta, credentials):
            continue
        out.append(
            {
                "code": code,
                "label": row.label or meta["label"],
                "kind": meta["kind"],
                "rate_source": meta["rate_source"],
                "priority": row.priority,
                "settings": _decode(row.settings),
            }
        )
    out.sort(key=lambda carrier: (carrier["priority"], carrier["label"]))
    return out
