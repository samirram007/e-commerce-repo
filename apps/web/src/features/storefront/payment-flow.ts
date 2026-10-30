/**
 * Finish an online payment for an order the API just created (checkout) or
 * re-opened (`POST /orders/{id}/pay`). `order.payment` names the gateway the
 * backend resolved; every outcome is verified server-side via /payment/confirm.
 */
import { confirmPayment } from "./api";
import { openRazorpay } from "./payment-clients";
import type { ShopOrder } from "./types";

export type PaymentOutcome =
  /** Paid (or nothing to collect, e.g. cash on delivery). */
  | { kind: "done"; order: ShopOrder }
  /** Stripe: render `StripePaymentForm` with these values to finish. */
  | { kind: "stripe"; order: ShopOrder; clientSecret: string; publishableKey: string }
  /** The shopper closed the provider window; the order stays pending. */
  | { kind: "cancelled"; order: ShopOrder };

export async function completePayment(
  order: ShopOrder,
  prefill: { name?: string; email?: string; contact?: string } = {},
): Promise<PaymentOutcome> {
  const payment = order.payment;
  if (!payment || !payment.client_payload) return { kind: "done", order };
  const payload = payment.client_payload;

  if (payment.provider === "razorpay") {
    const result = await openRazorpay({
      key: String(payload.key ?? ""),
      order_id: String(payload.order_id ?? ""),
      amount: Number(payload.amount ?? 0),
      currency: String(payload.currency ?? "INR"),
      prefill,
    });
    if (!result) return { kind: "cancelled", order };
    return { kind: "done", order: await confirmPayment(order.id, result) };
  }

  if (payment.provider === "stripe") {
    return {
      kind: "stripe",
      order,
      clientSecret: String(payload.client_secret ?? ""),
      publishableKey: String(payload.publishable_key ?? ""),
    };
  }

  // mock gateway (dev/test): confirm straight away — the API verifies it.
  return { kind: "done", order: await confirmPayment(order.id, { payment_id: "mock_payment" }) };
}
