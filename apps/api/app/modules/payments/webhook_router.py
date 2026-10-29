"""Public payment webhook routes — no auth; the provider signature is the auth.

Mounted by ``api/v1/router.py`` next to the admin gateway routes:

    POST /api/v1/payments/webhooks/{provider}/{company_id}

The raw body is read verbatim (``await request.body()``) because both
Razorpay and Stripe sign the exact bytes they send.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.unit_of_work import get_db
from app.modules.payments.webhooks import handle_webhook

router = APIRouter(prefix="/payments")


@router.post("/webhooks/{provider}/{company_id}")
async def provider_webhook(
    provider: str,
    company_id: str,
    request: Request,
    session: Session = Depends(get_db),
):
    raw_body = await request.body()
    return handle_webhook(
        session,
        provider=provider,
        company_id=company_id,
        raw_body=raw_body,
        headers=dict(request.headers),
    )