import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { Button, Card, EmptyState, ErrorBanner, PageHeader, Spinner, StatusBadge, Tabs } from "../../components/ui";
import { api } from "../../lib/api-client";
import { formatDate } from "../../lib/format";
import { usePermissions } from "../../hooks/use-permissions";
import { Stars } from "../storefront/ReviewsSection";

/**
 * Purchase feedback: the moderation queue for verified-purchase product
 * reviews (approval publishes a review and refreshes the product's rating) and
 * the private order-experience feedback (delivery / packaging / service).
 */
const reviewSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  order_id: z.string(),
  rating: z.number(),
  title: z.string().nullable(),
  body: z.string().nullable(),
  status: z.string(),
  created_at: z.string().nullable(),
  moderation_note: z.string().nullable().optional(),
  customer_id: z.string().nullable().optional(),
  product_name: z.string().nullable().optional(),
  sku: z.string().nullable().optional(),
});

const reviewsSchema = z.object({
  items: z.array(reviewSchema),
  counts: z.record(z.string(), z.number()),
});

const orderFeedbackSchema = z.object({
  id: z.string(),
  order_id: z.string(),
  delivery_rating: z.number().nullable(),
  packaging_rating: z.number().nullable(),
  service_rating: z.number().nullable(),
  comment: z.string().nullable(),
  created_at: z.string().nullable(),
});
type OrderFeedback = z.infer<typeof orderFeedbackSchema>;

const feedbackKeys = {
  reviews: (status: string) => ["feedback", "reviews", status] as const,
  orders: ["feedback", "orders"] as const,
};

type StatusTab = "pending" | "approved" | "rejected";

const TABS: { key: StatusTab; label: string }[] = [
  { key: "pending", label: "Awaiting approval" },
  { key: "approved", label: "Published" },
  { key: "rejected", label: "Rejected" },
];

function useReviews(status: StatusTab) {
  return useQuery({
    queryKey: feedbackKeys.reviews(status),
    queryFn: async () => {
      const { data } = await api.get("/feedback/reviews", { params: { status } });
      return reviewsSchema.parse(data);
    },
  });
}

function Rating({ value }: { value: number | null }) {
  return value ? <Stars rating={value} /> : <span className="muted">—</span>;
}

export function FeedbackPage() {
  const { has } = usePermissions();
  const canModerate = has("feedback.manage");
  const qc = useQueryClient();
  const [tab, setTab] = useState<StatusTab>("pending");

  const reviews = useReviews(tab);
  const orders = useQuery({
    queryKey: feedbackKeys.orders,
    queryFn: async (): Promise<OrderFeedback[]> => {
      const { data } = await api.get("/feedback/orders");
      return z.array(orderFeedbackSchema).parse(data);
    },
  });

  const moderate = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      const { data } = await api.patch(`/feedback/reviews/${id}`, { status });
      return reviewSchema.parse(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/feedback/reviews/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });

  const counts = reviews.data?.counts ?? {};
  const tabs = TABS.map((entry) => ({
    key: entry.key,
    label: counts[entry.key] ? `${entry.label} (${counts[entry.key]})` : entry.label,
  }));

  return (
    <>
      <PageHeader
        title="Purchase feedback"
        description="Verified-purchase reviews waiting for approval, and how shoppers rate their orders"
      />
      <ErrorBanner error={moderate.error ?? remove.error} />

      <Card>
        <Tabs tabs={tabs} active={tab} onChange={(key) => setTab(key as StatusTab)} />
      </Card>

      <Card title={tab === "pending" ? "Reviews awaiting approval" : "Reviews"}>
        {reviews.isLoading ? (
          <Spinner />
        ) : reviews.isError ? (
          <ErrorBanner error={reviews.error} />
        ) : (reviews.data?.items ?? []).length === 0 ? (
          <EmptyState
            title="Nothing here"
            message={
              tab === "pending"
                ? "No reviews are waiting for moderation."
                : "No reviews with this status yet."
            }
          />
        ) : (
          <div className="stack">
            {(reviews.data?.items ?? []).map((review) => (
              <div key={review.id} className="gateway-head" style={{ alignItems: "flex-start" }}>
                <div>
                  <div>
                    <Rating value={review.rating} />{" "}
                    <strong>{review.title || review.product_name || "Product review"}</strong>
                  </div>
                  <div className="muted">
                    {review.product_name ?? review.product_id}
                    {review.sku ? ` · ${review.sku}` : ""} · order {review.order_id.slice(0, 8)} ·{" "}
                    {review.created_at ? formatDate(review.created_at) : ""}
                  </div>
                  {review.body ? <p style={{ margin: "6px 0 0" }}>{review.body}</p> : null}
                  {review.moderation_note ? (
                    <div className="muted">Note: {review.moderation_note}</div>
                  ) : null}
                </div>
                <div className="gateway-actions" style={{ marginTop: 0 }}>
                  <StatusBadge status={review.status} />
                  {canModerate ? (
                    <>
                      {review.status !== "approved" ? (
                        <Button
                          variant="secondary"
                          disabled={moderate.isPending}
                          onClick={() => moderate.mutate({ id: review.id, status: "approved" })}
                        >
                          Approve
                        </Button>
                      ) : null}
                      {review.status !== "rejected" ? (
                        <Button
                          variant="secondary"
                          disabled={moderate.isPending}
                          onClick={() => moderate.mutate({ id: review.id, status: "rejected" })}
                        >
                          Reject
                        </Button>
                      ) : null}
                      <Button
                        variant="secondary"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(review.id)}
                      >
                        Delete
                      </Button>
                    </>
                  ) : (
                    <span className="muted">Read-only</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Order experience feedback">
        {orders.isLoading ? (
          <Spinner />
        ) : orders.isError ? (
          <ErrorBanner error={orders.error} />
        ) : (orders.data ?? []).length === 0 ? (
          <EmptyState title="No order feedback yet" message="Shoppers can rate delivery, packaging and service from their orders page." />
        ) : (
          <div className="stack">
            {(orders.data ?? []).map((row) => (
              <div key={row.id} className="gateway-head" style={{ alignItems: "flex-start" }}>
                <div>
                  <div className="muted">
                    Order {row.order_id.slice(0, 8)} · {row.created_at ? formatDate(row.created_at) : ""}
                  </div>
                  <div className="gateway-fields" style={{ marginTop: 6 }}>
                    <div>
                      <div className="muted">Delivery</div>
                      <Rating value={row.delivery_rating} />
                    </div>
                    <div>
                      <div className="muted">Packaging</div>
                      <Rating value={row.packaging_rating} />
                    </div>
                    <div>
                      <div className="muted">Service</div>
                      <Rating value={row.service_rating} />
                    </div>
                  </div>
                  {row.comment ? <p style={{ margin: "6px 0 0" }}>{row.comment}</p> : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
