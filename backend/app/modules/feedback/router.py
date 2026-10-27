"""Purchase feedback routes (ERP): review moderation and order experience.

Shoppers submit through the storefront; here the store sees what came in,
approves or rejects product reviews — approval is what publishes a review and
refreshes the product's star rating — and reads the private order feedback.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import P_FEEDBACK_MANAGE, P_FEEDBACK_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.catalog.models import Product
from app.modules.feedback import service as svc
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/feedback")


class ReviewModerationIn(BaseModel):
    status: str = Field(description="approved or rejected")
    note: str | None = Field(default=None, max_length=1000)


def _with_product(session: Session, company_id: str, rows: list) -> list[dict]:
    """Attach the product name/sku so the moderation list is readable."""
    products = {
        product.id: product
        for product in session.execute(
            select(Product).where(
                Product.company_id == company_id,
                Product.id.in_([row.product_id for row in rows] or [""]),
            )
        ).scalars()
    }
    out: list[dict] = []
    for row in rows:
        product = products.get(row.product_id)
        out.append(
            {
                **svc.review_out(row),
                "product_name": product.name if product is not None else None,
                "sku": product.sku if product is not None else None,
                "image_file_id": product.image_file_id if product is not None else None,
            }
        )
    return out


@router.get("/reviews")
def list_reviews(
    status: str | None = None,
    product_id: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_FEEDBACK_VIEW)),
    session: Session = Depends(get_db),
):
    """Product reviews, newest first (`status=pending` for the moderation queue)."""
    rows = svc.list_reviews(session, ctx.company_id, status=status, product_id=product_id)
    return {
        "items": _with_product(session, ctx.company_id, rows),
        "counts": {
            state: len(svc.list_reviews(session, ctx.company_id, status=state))
            for state in ("pending", "approved", "rejected")
        },
    }


@router.patch("/reviews/{review_id}")
def moderate_review(
    review_id: str,
    payload: ReviewModerationIn,
    ctx: CompanyCtx = Depends(guard(P_FEEDBACK_MANAGE)),
    session: Session = Depends(get_db),
):
    """Approve or reject a review; the product's rating follows immediately."""
    review = svc.get_review(session, ctx.company_id, review_id)
    svc.moderate(session, review, status=payload.status, note=payload.note)
    log_action(
        session,
        action="feedback.review.moderated",
        entity_type="product_review",
        entity_id=review.id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
        after_data={"status": review.status, "rating": review.rating},
    )
    return _with_product(session, ctx.company_id, [review])[0]


@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: str,
    ctx: CompanyCtx = Depends(guard(P_FEEDBACK_MANAGE)),
    session: Session = Depends(get_db),
):
    """Remove a review (spam); the product's rating is recomputed."""
    review = svc.get_review(session, ctx.company_id, review_id)
    svc.delete_review(session, review)
    log_action(
        session,
        action="feedback.review.deleted",
        entity_type="product_review",
        entity_id=review_id,
        actor_user_id=ctx.user.id,
        company_id=ctx.company_id,
    )
    return {"deleted": review_id}


@router.get("/orders")
def list_order_feedback(
    ctx: CompanyCtx = Depends(guard(P_FEEDBACK_VIEW)), session: Session = Depends(get_db)
):
    """Order-experience feedback (delivery, packaging, service), newest first."""
    return [svc.feedback_out(row) for row in svc.list_order_feedback(session, ctx.company_id)]
