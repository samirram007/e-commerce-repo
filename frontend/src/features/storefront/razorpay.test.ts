import { afterEach, describe, expect, it } from "vitest";

import { openRazorpayCheckout } from "./razorpay";
import type { RazorpayOrderIntent } from "./types";

const INTENT: RazorpayOrderIntent = {
  key_id: "rzp_test_key",
  razorpay_order_id: "order_123",
  amount: 118000,
  currency: "INR",
  order_id: "order-uuid",
  doc_number: "SO-0001",
  store_name: "Demo Retail Co",
  description: "Order SO-0001",
};

interface CheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  order_id: string;
  prefill?: { name?: string; email?: string; contact?: string };
  handler: (response: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => void;
  modal?: { ondismiss?: () => void };
}

function installRazorpay(open: (options: CheckoutOptions) => void): { options: CheckoutOptions | null } {
  const state: { options: CheckoutOptions | null } = { options: null };
  class FakeRazorpay {
    constructor(options: CheckoutOptions) {
      state.options = options;
    }
    on() {
      // no-op: the failure callback is not exercised here
    }
    open() {
      if (state.options) open(state.options);
    }
  }
  (globalThis as { window?: unknown }).window = { Razorpay: FakeRazorpay };
  return state;
}

describe("openRazorpayCheckout", () => {
  afterEach(() => {
    delete (globalThis as { window?: unknown }).window;
  });

  it("opens Checkout with the server gateway order and resolves the verified payload", async () => {
    const state = installRazorpay((options) =>
      options.handler({
        razorpay_order_id: "order_123",
        razorpay_payment_id: "pay_123",
        razorpay_signature: "sig_123",
      }),
    );

    const verified = await openRazorpayCheckout(INTENT, {
      name: "Asha",
      email: "asha@example.com",
    });

    expect(state.options?.key).toBe("rzp_test_key");
    expect(state.options?.amount).toBe(118000);
    expect(state.options?.currency).toBe("INR");
    expect(state.options?.order_id).toBe("order_123");
    expect(state.options?.name).toBe("Demo Retail Co");
    expect(state.options?.prefill).toEqual({ name: "Asha", email: "asha@example.com" });
    expect(verified).toEqual({
      razorpay_order_id: "order_123",
      razorpay_payment_id: "pay_123",
      razorpay_signature: "sig_123",
    });
  });

  it("rejects when the shopper dismisses the window", async () => {
    installRazorpay((options) => options.modal?.ondismiss?.());
    await expect(openRazorpayCheckout(INTENT, {})).rejects.toThrow("Payment was cancelled");
  });
});
