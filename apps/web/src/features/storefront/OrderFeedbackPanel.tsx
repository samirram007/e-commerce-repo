import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { orderFeedbackQueryOptions, shopKeys } from "./queries";
import { submitOrderFeedback, submitProductReview } from "./api";
import { Button, Spinner } from "../../components/ui";
import { Stars } from "./ReviewsSection";
import type { ShopOrder, ShopReviewableItem } from "./types";

/** Star picker for a 1–5 rating (0 = not chosen). */
function StarPicker({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (rating: number) => void;
  label: string;
}) {
  return (
    <div className="shop-star-picker" role="radiogroup" aria-label={label}>
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          aria-checked={value === star}
          aria-label={`${star} star${star === 1 ? "" : "s"}`}
          className={`shop-star-btn ${value >= star ? "on" : ""}`}
          onClick={() => onChange(star)}
        >
          ★
        </button>
      ))}
      {value > 0 ? <span className="muted">{value}/5</span> : <span className="muted">Not rated</span>}
    </div>
  );
}

interface ReviewDraft {
  rating: number;
  title: string;
  body: string;
}

function ReviewableRow({ item, orderId }: { item: ShopReviewableItem; orderId: string }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<ReviewDraft>({ rating: 0, title: "", body: "" });
  const [error, setError] = useState<unknown>(null);

  const submit = useMutation({
    mutationFn: () =>
      submitProductReview(orderId, {
        product_id: item.product_id,
        rating: draft.rating,
        title: draft.title.trim() || undefined,
        body: draft.body.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: shopKeys.orderFeedback(orderId) });
      qc.invalidateQueries({ queryKey: shopKeys.productReviews(item.product_id) });
      qc.invalidateQueries({ queryKey: shopKeys.product(item.product_id) });
    },
    onError: (cause) => setError(cause),
  });

  if (item.reviewed) {
    return (
      <div className="shop-feedback-item done">
        <span>
          {item.name}
          <span className="muted"> · {item.sku}</span>
        </span>
        <span className="muted">
          {item.review_status === "pending"
            ? `Review sent (${item.rating}★) — awaiting the store's approval`
            : `Reviewed (${item.rating}★)`}
        </span>
      </div>
    );
  }

  return (
    <div className="shop-feedback-item">
      <div className="shop-feedback-item-head">
        <span>
          {item.name}
          <span className="muted"> · {item.sku}</span>
        </span>
      </div>
      <StarPicker
        value={draft.rating}
        onChange={(rating) => setDraft((prev) => ({ ...prev, rating }))}
        label={`Rating for ${item.name}`}
      />
      <input
        className="shop-feedback-input"
        value={draft.title}
        maxLength={120}
        placeholder="Headline (optional)"
        onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
      />
      <textarea
        className="shop-feedback-textarea"
        value={draft.body}
        maxLength={4000}
        rows={2}
        placeholder="How was the item? (optional)"
        onChange={(event) => setDraft((prev) => ({ ...prev, body: event.target.value }))}
      />
      {error ? <p className="error-text">{(error as Error).message}</p> : null}
      <Button
        variant="secondary"
        onClick={() => submit.mutate()}
        disabled={draft.rating === 0 || submit.isPending}
      >
        {submit.isPending ? "Sending…" : "Send review"}
      </Button>
    </div>
  );
}

/**
 * Shoppers review the items of a paid order (each review is published once the
 * store approves it) and rate the order experience: delivery, packaging and
 * service. The ERP sees the reviews in Feedback and the experience privately.
 */
export function OrderFeedbackPanel({ order, onClose }: { order: ShopOrder; onClose: () => void }) {
  const qc = useQueryClient();
  const state = useQuery(orderFeedbackQueryOptions(order.id));
  const [experience, setExperience] = useState({
    delivery: 0,
    packaging: 0,
    service: 0,
    comment: "",
  });
  const [error, setError] = useState<unknown>(null);

  const existing = state.data?.order_feedback;
  useEffect(() => {
    if (!existing) return;
    setExperience({
      delivery: existing.delivery_rating ?? 0,
      packaging: existing.packaging_rating ?? 0,
      service: existing.service_rating ?? 0,
      comment: existing.comment ?? "",
    });
  }, [existing]);

  const save = useMutation({
    mutationFn: () =>
      submitOrderFeedback(order.id, {
        delivery_rating: experience.delivery || undefined,
        packaging_rating: experience.packaging || undefined,
        service_rating: experience.service || undefined,
        comment: experience.comment.trim() || undefined,
      }),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: shopKeys.orderFeedback(order.id) });
    },
    onError: (cause) => setError(cause),
  });

  const items = state.data?.items ?? [];

  return (
    <div className="shop-feedback">
      <div className="shop-return-form-head">
        <strong>Order {order.doc_number}</strong>
        <span className="muted">
          Reviews appear on the product page once the store approves them.
        </span>
      </div>

      {state.isLoading ? <Spinner /> : null}
      <Stars rating={0} className="visually-hidden" />

      {state.data && !state.data.can_review ? (
        <p className="muted">Items can be reviewed once this order is paid.</p>
      ) : null}

      {state.data?.can_review ? (
        <div className="shop-feedback-items">
          {items.map((item) => (
            <ReviewableRow key={item.product_id} item={item} orderId={order.id} />
          ))}
        </div>
      ) : null}

      <div className="shop-feedback-item">
        <div className="shop-feedback-item-head">
          <strong>How was the order?</strong>
          <span className="muted">Delivery, packaging and service — shared with the store only.</span>
        </div>
        <StarPicker
          value={experience.delivery}
          onChange={(delivery) => setExperience((prev) => ({ ...prev, delivery }))}
          label="Delivery rating"
        />
        <span className="muted">Delivery</span>
        <StarPicker
          value={experience.packaging}
          onChange={(packaging) => setExperience((prev) => ({ ...prev, packaging }))}
          label="Packaging rating"
        />
        <span className="muted">Packaging</span>
        <StarPicker
          value={experience.service}
          onChange={(service) => setExperience((prev) => ({ ...prev, service }))}
          label="Service rating"
        />
        <span className="muted">Service</span>
        <textarea
          className="shop-feedback-textarea"
          value={experience.comment}
          maxLength={2000}
          rows={2}
          placeholder="Anything else the store should know? (optional)"
          onChange={(event) => setExperience((prev) => ({ ...prev, comment: event.target.value }))}
        />
        {error ? <p className="error-text">{(error as Error).message}</p> : null}
        {existing ? (
          <p className="muted">
            You already rated this order — sending again updates your feedback.
          </p>
        ) : null}
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Saving…" : existing ? "Update feedback" : "Send feedback"}
        </Button>
      </div>

      <div className="shop-return-actions">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}
