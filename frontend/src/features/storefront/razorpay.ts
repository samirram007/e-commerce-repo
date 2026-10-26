/** Razorpay Checkout (hosted) — script loading and a promise wrapper. */
import type { RazorpayOrderIntent, RazorpayVerifyPayload } from "./types";

interface RazorpayCheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  order_id: string;
  prefill?: { name?: string; email?: string; contact?: string };
  theme?: { color?: string };
  handler: (response: RazorpayVerifyPayload) => void;
  modal?: { ondismiss?: () => void };
}

interface RazorpayInstance {
  open: () => void;
  on: (event: string, handler: (response: unknown) => void) => void;
}

type RazorpayConstructor = new (options: RazorpayCheckoutOptions) => RazorpayInstance;

const SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

let loading: Promise<void> | null = null;

/** Inject Checkout.js once per page. */
export function loadRazorpay(): Promise<void> {
  const win = window as typeof window & { Razorpay?: RazorpayConstructor };
  if (win.Razorpay) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      loading = null;
      reject(new Error("Could not load Razorpay Checkout"));
    };
    document.body.appendChild(script);
  });
  return loading;
}

/**
 * Opens the Razorpay modal for a gateway order and resolves with the payment
 * fields the server must verify. Rejects when the shopper dismisses the modal
 * or the payment fails — the order stays unpaid and can be paid from Orders.
 */
export async function openRazorpayCheckout(
  intent: RazorpayOrderIntent,
  prefill: { name?: string; email?: string; contact?: string },
): Promise<RazorpayVerifyPayload> {
  await loadRazorpay();
  const RazorpayCtor = (window as typeof window & { Razorpay?: RazorpayConstructor }).Razorpay;
  if (!RazorpayCtor) throw new Error("Razorpay Checkout is unavailable");

  return new Promise<RazorpayVerifyPayload>((resolve, reject) => {
    const checkout = new RazorpayCtor({
      key: intent.key_id,
      amount: intent.amount,
      currency: intent.currency,
      name: intent.store_name,
      description: intent.description,
      order_id: intent.razorpay_order_id,
      prefill,
      theme: { color: "#2f54eb" },
      handler: (response) => resolve(response),
      modal: { ondismiss: () => reject(new Error("Payment was cancelled")) },
    });
    checkout.on("payment.failed", (response) => {
      const description = (response as { error?: { description?: string } })?.error?.description;
      reject(new Error(description || "Payment failed"));
    });
    checkout.open();
  });
}
