"""Purchase feedback service: verified-purchase reviews and order feedback.

Ownership is checked by the caller (the storefront knows the shopper's cart
token / account); this module owns the rules and the aggregation:

- a review must belong to a line of a *paid* order,
- one review per purchased item, no editing after submission,
- only `approved` reviews count towards a product's star rating,
- one order-experience feedback per order, edited in place on a second submit.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.catalog.models import Product
from app.modules.feedback.models import (
    MAX_RATING,
    MIN_RATING,
    REVIEW_STATUSES,
    OrderFeedback,
    ProductReview,
)
from app.modules.sales.models import SalesOrder
from app.shared.money import dec, money


def _rating(value, field: str, *, required: bool) -> int | None:
    """Validate a 1–5 star rating (None when optional and not sent)."""
    if value is None or value == "":
        if required:
            raise BusinessRuleError("BAD_RATING", f"{field} is required (1–5 stars)")
        return None
    try:
        rating = int(value)
    except (TypeError, ValueError) as exc:
        raise BusinessRuleError("BAD_RATING", f"{field} must be a whole number of stars") from exc
    if rating < MIN_RATING or rating > MAX_RATING:
        raise BusinessRuleError("BAD_RATING", f"{field} must be between {MIN_RATING} and {MAX_RATING}")
    return rating


def _order(session: Session, company_id: str, order_id: str) -> SalesOrder:
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Order")
    return order


def reviewable_lines(session: Session, order: SalesOrder) -> list[dict]:
    """The order's lines the shopper may review, with what is already reviewed.

    Only paid orders are reviewable — the review has to come from a purchase.
    """
    from app.modules.sales.service import get_order_lines

    existing = {
        row.product_id: row
        for row in session.execute(
            select(ProductReview).where(
                ProductReview.order_id == order.id, ProductReview.company_id == order.company_id
            )
        ).scalars()
    }
    out: list[dict] = []
    for line in get_order_lines(session, order.id):
        review = existing.get(line.product_id)
        product = session.get(Product, line.product_id)
        out.append(
            {
                "product_id": line.product_id,
                "order_line_id": line.id,
                "sku": line.sku_snapshot,
                "name": line.description_snapshot,
                "qty": str(line.qty),
                "image_file_id": product.image_file_id if product is not None else None,
                "reviewed": review is not None,
                "review_status": review.status if review is not None else None,
                "rating": review.rating if review is not None else None,
                "review_id": review.id if review is not None else None,
            }
        )
    return out


def submit_review(
    session: Session,
    *,
    company_id: str,
    order_id: str,
    product_id: str,
    rating,
    title: str | None = None,
    body: str | None = None,
    owner_key: str | None = None,
    customer_id: str | None = None,
) -> ProductReview:
    """Record a verified-purchase review (pending store approval)."""
    order = _order(session, company_id, order_id)
    if order.payment_state != "paid":
        raise BusinessRuleError(
            "NOT_PURCHASED", "Reviews can be written once the order is paid"
        )
    from app.modules.sales.service import get_order_lines

    line = next(
        (row for row in get_order_lines(session, order.id) if row.product_id == product_id), None
    )
    if line is None:
        raise NotFoundError("Order line")
    duplicate = session.scalar(
        select(ProductReview.id).where(
            ProductReview.order_id == order.id, ProductReview.product_id == product_id
        )
    )
    if duplicate:
        raise ConflictError(
            "ALREADY_REVIEWED", "You have already reviewed this item from this order"
        )
    review = ProductReview(
        company_id=company_id,
        product_id=product_id,
        order_id=order.id,
        order_line_id=line.id,
        customer_id=customer_id or order.customer_id,
        owner_key=owner_key,
        rating=_rating(rating, "Rating", required=True),
        title=(title or "").strip()[:120] or None,
        body=(body or "").strip() or None,
        status="pending",
    )
    session.add(review)
    session.flush()
    return review


def submit_order_feedback(
    session: Session,
    *,
    company_id: str,
    order_id: str,
    delivery_rating=None,
    packaging_rating=None,
    service_rating=None,
    comment: str | None = None,
    owner_key: str | None = None,
    customer_id: str | None = None,
) -> OrderFeedback:
    """Order-experience feedback: delivery, packaging, service (one per order)."""
    order = _order(session, company_id, order_id)
    delivery = _rating(delivery_rating, "Delivery rating", required=False)
    packaging = _rating(packaging_rating, "Packaging rating", required=False)
    service = _rating(service_rating, "Service rating", required=False)
    if delivery is None and packaging is None and service is None and not (comment or "").strip():
        raise BusinessRuleError(
            "EMPTY_FEEDBACK", "Rate the delivery, the packaging or the service (or add a comment)"
        )
    row = session.scalar(select(OrderFeedback).where(OrderFeedback.order_id == order.id))
    if row is None:
        row = OrderFeedback(
            company_id=company_id, order_id=order.id, owner_key=owner_key, created_by=None
        )
        session.add(row)
    row.customer_id = customer_id or order.customer_id
    row.owner_key = owner_key or row.owner_key
    row.delivery_rating = delivery
    row.packaging_rating = packaging
    row.service_rating = service
    row.comment = (comment or "").strip() or None
    session.flush()
    return row


def order_feedback(session: Session, company_id: str, order_id: str) -> OrderFeedback | None:
    return session.scalar(
        select(OrderFeedback).where(
            OrderFeedback.company_id == company_id, OrderFeedback.order_id == order_id
        )
    )


def order_reviews(session: Session, company_id: str, order_id: str) -> list[ProductReview]:
    return list(
        session.execute(
            select(ProductReview)
            .where(ProductReview.company_id == company_id, ProductReview.order_id == order_id)
            .order_by(ProductReview.created_at)
        ).scalars()
    )


def list_order_feedback(session: Session, company_id: str, *, limit: int = 200) -> list[OrderFeedback]:
    return list(
        session.execute(
            select(OrderFeedback)
            .where(OrderFeedback.company_id == company_id)
            .order_by(OrderFeedback.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def product_reviews(
    session: Session, company_id: str, product_id: str, *, status: str = "approved", limit: int = 50
) -> list[ProductReview]:
    query = select(ProductReview).where(
        ProductReview.company_id == company_id, ProductReview.product_id == product_id
    )
    if status != "all":
        query = query.where(ProductReview.status == status)
    return list(
        session.execute(query.order_by(ProductReview.created_at.desc()).limit(limit)).scalars()
    )


def list_reviews(
    session: Session, company_id: str, *, status: str | None = None, product_id: str | None = None,
    limit: int = 200,
) -> list[ProductReview]:
    query = select(ProductReview).where(ProductReview.company_id == company_id)
    if status:
        query = query.where(ProductReview.status == status)
    if product_id:
        query = query.where(ProductReview.product_id == product_id)
    return list(
        session.execute(query.order_by(ProductReview.created_at.desc()).limit(limit)).scalars()
    )


def summary(session: Session, company_id: str, product_id: str) -> dict:
    """Approved rating summary for one product (what the storefront shows)."""
    average, count = session.execute(
        select(func.avg(ProductReview.rating), func.count())
        .select_from(ProductReview)
        .where(
            ProductReview.company_id == company_id,
            ProductReview.product_id == product_id,
            ProductReview.status == "approved",
        )
    ).one()
    return {
        "average": str(money(dec(average), 2)) if average is not None else None,
        "count": int(count or 0),
    }


def refresh_product_rating(session: Session, product: Product) -> None:
    """Recompute a product's star rating from its approved reviews."""
    stats = summary(session, product.company_id, product.id)
    product.rating_avg = dec(stats["average"]) if stats["average"] is not None else None
    product.rating_count = stats["count"]
    session.flush()


def get_review(session: Session, company_id: str, review_id: str) -> ProductReview:
    row = session.get(ProductReview, review_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Review")
    return row


def moderate(
    session: Session, review: ProductReview, *, status: str, note: str | None = None
) -> ProductReview:
    """Approve or reject a review; the product's rating follows immediately."""
    if status not in REVIEW_STATUSES:
        raise BusinessRuleError(
            "BAD_REVIEW_STATUS", f"Status must be one of {', '.join(REVIEW_STATUSES)}"
        )
    review.status = status
    review.moderation_note = (note or "").strip() or None
    review.moderated_at = datetime.now(timezone.utc)
    session.flush()
    product = session.get(Product, review.product_id)
    if product is not None:
        refresh_product_rating(session, product)
    return review


def delete_review(session: Session, review: ProductReview) -> None:
    product = session.get(Product, review.product_id)
    session.delete(review)
    session.flush()
    if product is not None:
        refresh_product_rating(session, product)


def review_out(review: ProductReview, *, shopper: bool = False) -> dict:
    out = {
        "id": review.id,
        "product_id": review.product_id,
        "order_id": review.order_id,
        "rating": review.rating,
        "title": review.title,
        "body": review.body,
        "status": review.status,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }
    if not shopper:
        out["moderation_note"] = review.moderation_note
        out["customer_id"] = review.customer_id
    return out


def feedback_out(row: OrderFeedback) -> dict:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "delivery_rating": row.delivery_rating,
        "packaging_rating": row.packaging_rating,
        "service_rating": row.service_rating,
        "comment": row.comment,
        "customer_id": row.customer_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
