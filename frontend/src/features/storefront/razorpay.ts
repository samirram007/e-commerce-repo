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

/** Literal signature the demo gateway accepts (see `payments/razorpay.py`). */
const DEMO_SIGNATURE = "demo";

/**
 * Payment fields for a demo payment. The server only accepts these while the
 * gateway runs in demo mode, so the signature never authenticates a real one.
 */
export function demoPaymentPayload(intent: RazorpayOrderIntent): RazorpayVerifyPayload {
  const suffix =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 16)
      : Math.random().toString(36).slice(2, 18);
  return {
    razorpay_order_id: intent.razorpay_order_id,
    razorpay_payment_id: `pay_demo_${suffix}`,
    razorpay_signature: DEMO_SIGNATURE,
  };
}

/**
 * Stand-in for the hosted Checkout window when the backend runs in demo mode:
 * a small dialog that confirms (or cancels) the payment, then returns the
 * fields the server verifies.
 */
function openDemoCheckout(intent: RazorpayOrderIntent): Promise<RazorpayVerifyPayload> {
  return new Promise<RazorpayVerifyPayload>((resolve, reject) => {
    const amount = (intent.amount / 100).toLocaleString("en-IN", {
      style: "currency",
      currency: intent.currency,
    });

    const overlay = document.createElement("div");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Demo Razorpay checkout");
    Object.assign(overlay.style, {
      position: "fixed",
      inset: "0",
      zIndex: "1000",
      display: "grid",
      placeItems: "center",
      padding: "24px",
      background: "rgba(15, 23, 42, 0.55)",
      backdropFilter: "blur(2px)",
    } as Partial<CSSStyleDeclaration>);

    const card = document.createElement("div");
    Object.assign(card.style, {
      width: "min(380px, 100%)",
      padding: "24px",
      borderRadius: "18px",
      background: "#ffffff",
      color: "#0f172a",
      boxShadow: "0 24px 60px -20px rgba(15, 23, 42, 0.55)",
      fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif",
      display: "grid",
      gap: "10px",
    } as Partial<CSSStyleDeclaration>);

    const title = document.createElement("strong");
    title.textContent = "Demo Razorpay checkout";
    title.style.fontSize = "17px";

    const line = document.createElement("p");
    line.textContent = `${intent.store_name} · ${intent.description}`;
    line.style.margin = "0";
    line.style.color = "#52525b";
    line.style.fontSize = "13px";

    const total = document.createElement("p");
    total.textContent = amount;
    total.style.margin = "4px 0 8px";
    total.style.fontSize = "26px";
    total.style.fontWeight = "700";

    const actions = document.createElement("div");
    Object.assign(actions.style, { display: "flex", gap: "10px", marginTop: "6px" });

    const pay = document.createElement("button");
    pay.type = "button";
    pay.textContent = `Pay ${amount}`;
    Object.assign(pay.style, {
      flex: "1",
      padding: "11px 16px",
      border: "0",
      borderRadius: "10px",
      background: "#2f54eb",
      color: "#ffffff",
      fontWeight: "600",
      cursor: "pointer",
    } as Partial<CSSStyleDeclaration>);

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    Object.assign(cancel.style, {
      padding: "11px 16px",
      border: "1px solid #e2e8f0",
      borderRadius: "10px",
      background: "#ffffff",
      color: "#0f172a",
      cursor: "pointer",
    } as Partial<CSSStyleDeclaration>);

    function close() {
      overlay.remove();
      document.removeEventListener("keydown", onKeyDown);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        close();
        reject(new Error("Payment was cancelled"));
      }
    }

    pay.addEventListener("click", () => {
      close();
      resolve(demoPaymentPayload(intent));
    });
    cancel.addEventListener("click", () => {
      close();
      reject(new Error("Payment was cancelled"));
    });
    document.addEventListener("keydown", onKeyDown);

    actions.append(pay, cancel);
    card.append(title, line, total, actions);
    overlay.append(card);
    document.body.append(overlay);
    pay.focus();
  });
}

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
  // Demo mode never loads Razorpay's script: there are no real keys to use.
  if (intent.demo) return openDemoCheckout(intent);

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
