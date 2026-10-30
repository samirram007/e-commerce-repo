import { useQuery } from "@tanstack/react-query";
import { productReviewsQueryOptions } from "./queries";
import { Spinner } from "../../components/ui";
import { formatDate } from "../../lib/format";

/** ★/☆ row for a 1–5 rating. */
export function Stars({ rating, className }: { rating: number; className?: string }) {
  const rounded = Math.round(rating);
  return (
    <span className={className} aria-label={`${rating} out of 5`}>
      <span className="shop-stars">{"★".repeat(Math.max(0, Math.min(5, rounded)))}</span>
      <span className="shop-stars-empty">{"★".repeat(Math.max(0, 5 - rounded))}</span>
    </span>
  );
}

/**
 * Approved reviews for a product (pending ones never reach the storefront).
 * Shoppers write reviews from their orders page, so the purchase is verified.
 */
export function ReviewsSection({ productId }: { productId: string }) {
  const reviews = useQuery(productReviewsQueryOptions(productId));

  if (reviews.isLoading) return <Spinner />;

  const summary = reviews.data?.summary;
  const items = reviews.data?.items ?? [];
  const average = summary?.average ? Number(summary.average) : 0;

  return (
    <section className="shop-reviews">
      <div className="shop-reviews-head">
        <h2>Customer reviews</h2>
        {summary && summary.count > 0 ? (
          <span className="shop-reviews-summary">
            <Stars rating={average} />
            <span className="muted">
              {average.toFixed(1)} out of 5 · {summary.count} review{summary.count === 1 ? "" : "s"}
            </span>
          </span>
        ) : null}
      </div>

      {items.length === 0 ? (
        <p className="muted">
          No reviews yet. Buyers can review this item from their orders page once the order is paid.
        </p>
      ) : (
        <div className="shop-review-list">
          {items.map((review) => (
            <article key={review.id} className="shop-review">
              <div className="shop-review-head">
                <Stars rating={review.rating} />
                <span className="muted">{review.created_at ? formatDate(review.created_at) : ""}</span>
              </div>
              {review.title ? <strong>{review.title}</strong> : null}
              {review.body ? <p className="shop-review-body">{review.body}</p> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
