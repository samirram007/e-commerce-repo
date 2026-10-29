/**
 * Hosted checkout helpers for the storefront.
 *
 * Both provider scripts are lazy-loaded on first use so the shop never pays
 * for gateways it doesn't offer. Only publishable data (key_id / pk_) ever
 * reaches the browser — secrets stay server-side.
 */

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

let razorpayPromise: Promise<boolean> | null = null;

/** Load checkout.js once; resolves false when the CDN is unreachable. */
export function loadRazorpayScript(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (window.Razorpay) return Promise.resolve(true);
  if (!razorpayPromise) {
    razorpayPromise = new Promise<boolean>((resolve) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => {
        razorpayPromise = null;
        resolve(false);
      };
      document.body.appendChild(script);
    });
  }
  return razorpayPromise;
}

export interface RazorpayHandlerResult {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

/**
 * Open the Razorpay modal. Resolves with the handler result, or `null` when
 * the shopper dismisses it (the order stays pending and can be retried).
 */
export async function openRazorpay(options: {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name?: string;
  prefill?: { name?: string; email?: string; contact?: string };
}): Promise<RazorpayHandlerResult | null> {
  const loaded = await loadRazorpayScript();
  const RazorpayCtor = window.Razorpay;
  if (!loaded || !RazorpayCtor) {
    throw new Error("Could not load the Razorpay checkout. Check your connection and try again.");
  }
  return new Promise<RazorpayHandlerResult | null>((resolve) => {
    let settled = false;
    const settle = (value: RazorpayHandlerResult | null) => {
      if (!settled) {
        settled = true;
        resolve(value);
      }
    };
    const instance = new RazorpayCtor({
      ...options,
      handler: (response: RazorpayHandlerResult) => settle(response),
      modal: { ondismiss: () => settle(null) },
    });
    instance.open();
  });
}