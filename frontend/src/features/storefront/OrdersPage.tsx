import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelOrder,
  createRazorpayOrder,
  payOrder,
  requestOrderReturn,
  verifyRazorpayPayment,
} from "./api";
import {
  orderReturnsQueryOptions,
  ordersQueryOptions,
  paymentMethodsQueryOptions,
  shopKeys,
} from "./queries";
import { openRazorpayCheckout } from "./razorpay";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import { useStoreCurrency } from "./store-context";
import type { ShopOrder } from "./types";

/** Shopper-facing explanation for why an order was cancelled. */
const CANCEL_REASONS: Record<string, string> = {
  payment_timeout: "Payment was not completed in time, so the order was released.",
  cancelled_by_customer: "You cancelled this order.",
  cancelled_by_staff: "The store cancelled this order.",
};

function cancelReasonText(reason?: string | null): string | null {
  return reason ? CANCEL_REASONS[reason] ?? null : null;
}

function OrderReturns({ orderId }: { orderId: string }) {
  const returns = useQuery(orderReturnsQueryOptions(orderId));
  if (!returns.data || returns.data.length === 0) return null;
  return (
    <div className="shop-order-returns">
      {returns.data.map((row) => (
        <div key={row.id} className="shop-order-return">
          <span>
            Return <strong>{row.doc_number}</strong>
            <span className="muted">
              {" · "}
              {row.lines.reduce((sum, line) => sum + Number(line.qty), 0)} item(s)
            </span>
          </span>
          <span className={`badge ${row.status === "completed" ? "ok" : row.status === "rejected" ? "bad" : "warn"}`}>
            {row.status}
          </span>
        </div>
      ))}
    </div>
  );
}

function ReturnAction({ order, onOpen }: { order: ShopOrder; onOpen: () => void }) {
  const returns = useQuery(orderReturnsQueryOptions(order.id));
  const returned: Record<string, number> = {};
  for (const row of returns.data ?? []) {
    if (!["requested", "approved", "completed"].includes(row.status)) continue;
    for (const line of row.lines) {
      returned[line.product_id] = (returned[line.product_id] ?? 0) + Number(line.qty);
    }
  }
  const anyRemaining = order.items.some(
    (item) => Number(item.qty) > (returned[item.product_id] ?? 0),
  );
  if (!anyRemaining) return null;
  return (
    <Button variant="secondary" onClick={onOpen}>
      Return items
    </Button>
  );
}

function ReturnForm({ order, onClose }: { order: ShopOrder; onClose: () => void }) {
  const qc = useQueryClient();
  const returns = useQuery(orderReturnsQueryOptions(order.id));
  const [qty, setQty] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<unknown>(null);

  // Items already returned (or awaiting approval) cannot be returned again.
  const alreadyReturned = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const row of returns.data ?? []) {
      if (!["requested", "approved", "completed"].includes(row.status)) continue;
      for (const line of row.lines) {
        counts[line.product_id] = (counts[line.product_id] ?? 0) + Number(line.qty);
      }
    }
    return counts;
  }, [returns.data]);

  const remainingFor = (productId: string, ordered: string) =>
    Math.max(0, Number(ordered) - (alreadyReturned[productId] ?? 0));

  const submit = useMutation({
    mutationFn: () =>
      requestOrderReturn(
        order.id,
        Object.entries(qty)
          .map(([product_id, value]) => ({ product_id, qty: Number(value) }))
          .filter((line) => {
            const item = order.items.find((entry) => entry.product_id === line.product_id);
            const max = item ? remainingFor(item.product_id, item.qty) : 0;
            return Number.isFinite(line.qty) && line.qty > 0 && line.qty <= max;
          }),
        notes.trim() || undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: shopKeys.orderReturns(order.id) });
      qc.invalidateQueries({ queryKey: shopKeys.orders });
      onClose();
    },
    onError: (cause) => setError(cause),
  });

  const chosen = order.items.filter((item) => {
    const value = Number(qty[item.product_id] ?? 0);
    return value > 0 && value <= remainingFor(item.product_id, item.qty);
  }).length;

  return (
    <div className="shop-return-form">
      <div className="shop-return-form-head">
        <strong>Return items</strong>
        <span className="muted">Choose quantities — approvals happen in the ERP.</span>
      </div>
      {order.items.map((item) => {
        const remaining = remainingFor(item.product_id, item.qty);
        return (
          <label key={item.product_id} className="shop-return-item">
            <span>
              {item.name}
              <span className="muted">
                {remaining === 0 ? " · already returned" : ` · up to ${remaining}`}
              </span>
            </span>
            <input
              type="number"
              min="0"
              max={remaining}
              value={qty[item.product_id] ?? ""}
              onChange={(e) => setQty({ ...qty, [item.product_id]: e.target.value })}
              className="shop-qty-input"
              placeholder="0"
              disabled={remaining === 0}
            />
          </label>
        );
      })}
      <input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Reason (optional)"
        className="shop-return-notes"
        maxLength={500}
      />
      {error ? <p className="error-text">{(error as Error).message}</p> : null}
      <div className="shop-return-actions">
        <Button variant="secondary" onClick={onClose} disabled={submit.isPending}>
          Cancel
        </Button>
        <Button onClick={() => submit.mutate()} disabled={submit.isPending || chosen === 0}>
          {submit.isPending ? "Requesting…" : "Request return"}
        </Button>
      </div>
    </div>
  );
}

export function OrdersPage() {
  const qc = useQueryClient();
  const currency = useStoreCurrency();
  const orders = useQuery(ordersQueryOptions());
  const paymentMethods = useQuery(paymentMethodsQueryOptions());
  const razorpayAvailable = (paymentMethods.data ?? []).some(
    (method) => method.code === "razorpay" && method.available,
  );

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [confirmCancel, setConfirmCancel] = useState<string | null>(null);
  const [returning, setReturning] = useState<string | null>(null);

  const cancel = useMutation({
    mutationFn: (orderId: string) => cancelOrder(orderId),
    onMutate: (orderId) => setBusy(orderId),
    onSettled: () => setBusy(null),
    onSuccess: () => {
      setConfirmCancel(null);
      qc.invalidateQueries({ queryKey: shopKeys.orders });
    },
    onError: (cause) => setError(cause),
  });

  async function pay(order: ShopOrder) {
    setError(null);
    setBusy(order.id);
    try {
      if (razorpayAvailable) {
        const intent = await createRazorpayOrder(order.id);
        const verified = await openRazorpayCheckout(intent, {});
        await verifyRazorpayPayment(order.id, verified);
      } else {
        await payOrder(order.id, "card");
      }
      qc.invalidateQueries({ queryKey: shopKeys.orders });
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(null);
    }
  }

  if (orders.isLoading) return <Spinner />;
  if (orders.isError) return <EmptyState title="Could not load orders" message={(orders.error as Error).message} />;
  const list = orders.data ?? [];

  if (list.length === 0) {
    return (
      <div className="shop-page">
        <h1 className="page-title">Your orders</h1>
        <EmptyState title="No orders yet" message="Place an order to see it here." />
      </div>
    );
  }

  return (
    <div className="shop-page">
      <h1 className="page-title">Your orders</h1>
      {error ? <p className="error-text">{(error as Error).message}</p> : null}

      <div className="shop-orders">
        {list.map((order) => {
          const codPending =
            order.payment_method === "cod" && order.payment_status === "pending";
          const payable = order.payment_state !== "paid" && order.status === "pending_payment";
          const cancellable = ["pending_payment", "paid", "confirmed", "fulfilling"].includes(order.status);
          const returnable = order.status === "delivered" && order.payment_state === "paid";
          const isBusy = busy === order.id;

          return (
            <div key={order.id} className="card shop-order-card">
              <div className="shop-order-head">
                <div>
                  <strong>{order.doc_number}</strong>
                  <span className="muted"> · {new Date(order.order_date).toLocaleDateString()}</span>
                </div>
                <div className="shop-order-badges">
                  <span className={`badge ${order.status === "delivered" || order.status === "paid" ? "ok" : "warn"}`}>
                    {order.status}
                  </span>
                  <span className={`badge ${order.payment_state === "paid" ? "ok" : order.payment_state === "refunded" ? "bad" : "warn"}`}>
                    {codPending ? "pay on delivery" : order.payment_state}
                  </span>
                </div>
              </div>

              <div className="shop-order-items">
                {order.items.map((item, idx) => (
                  <div key={idx} className="shop-order-item">
                    <span>{item.name}</span>
                    <span className="muted">
                      ×{Number(item.qty)} · {formatMoney(item.line_total, currency)}
                    </span>
                  </div>
                ))}
              </div>

              {order.status === "cancelled" ? (
                <div className="shop-order-cancelled">
                  <span className="badge bad">cancelled</span>
                  <span className="muted shop-order-hint">
                    {cancelReasonText(order.cancel_reason) ?? "This order was cancelled."}
                  </span>
                </div>
              ) : null}
              {order.payment_state === "refunded" ? (
                <p className="shop-order-hint muted">The amount was refunded to your account.</p>
              ) : null}

              <div className="shop-order-foot">
                <span className="muted">Total</span>
                <strong>{formatMoney(order.total, order.currency || currency)}</strong>
              </div>

              <OrderReturns orderId={order.id} />

              <div className="shop-order-actions">
                {payable ? (
                  <Button onClick={() => pay(order)} disabled={isBusy}>
                    {isBusy ? "Opening payment…" : `Pay now${razorpayAvailable ? "" : " (sandbox)"}`}
                  </Button>
                ) : null}

                {cancellable && confirmCancel !== order.id ? (
                  <Button variant="secondary" onClick={() => setConfirmCancel(order.id)} disabled={isBusy}>
                    {order.payment_state === "paid" ? "Cancel & refund" : "Cancel order"}
                  </Button>
                ) : null}

                {confirmCancel === order.id ? (
                  <div className="shop-order-confirm">
                    <span className="muted">
                      {order.payment_state === "paid"
                        ? "This refunds the payment and credits the invoice."
                        : "This releases the reserved stock."}
                    </span>
                    <Button variant="danger" onClick={() => cancel.mutate(order.id)} disabled={isBusy}>
                      {isBusy ? "Cancelling…" : "Confirm cancel"}
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirmCancel(null)} disabled={isBusy}>
                      Keep order
                    </Button>
                  </div>
                ) : null}

                {codPending ? (
                  <span className="muted shop-order-hint">
                    Pay {formatMoney(order.total, order.currency || currency)} in cash when it arrives.
                  </span>
                ) : null}

                {returnable && returning !== order.id ? (
                  <ReturnAction order={order} onOpen={() => setReturning(order.id)} />
                ) : null}
              </div>

              {returning === order.id ? (
                <ReturnForm order={order} onClose={() => setReturning(null)} />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
