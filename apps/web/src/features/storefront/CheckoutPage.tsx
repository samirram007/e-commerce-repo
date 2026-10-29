import { useMemo, useState, type FormEvent, type ComponentType } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Banknote, CreditCard, Lock, ShoppingBag, Smartphone } from "lucide-react";
import { z } from "zod";
import { SheetSelect } from "../../components/sheet";
import { Badge, ErrorBanner } from "../../components/ui";
import { fieldErrors } from "../../lib/zod-utils";
import { EmptyState, ImagePlaceholder, money, PageHero } from "./components";
import { productImage } from "./demo-catalog";
import { confirmPayment, placeOrder } from "./api";
import { paymentMethodsQueryOptions } from "./queries";
import { openRazorpay } from "./payment-clients";
import { OrderSummary } from "./CartPage";
import { useShop } from "./shop-state";
import type { ShopOrder } from "./types";

const STATES = [
  "Andhra Pradesh", "Assam", "Bihar", "Delhi", "Goa", "Gujarat", "Haryana", "Karnataka", "Kerala",
  "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
  "Uttar Pradesh", "Uttarakhand", "West Bengal",
].map((name) => ({ value: name, label: name }));

const PAYMENT_METHODS = [
  { code: "upi", label: "UPI", hint: "GPay, PhonePe, Paytm", icon: Smartphone },
  { code: "card", label: "Credit / Debit card", hint: "Visa, Mastercard, RuPay", icon: CreditCard },
  { code: "cod", label: "Cash on delivery", hint: "Pay when it arrives", icon: Banknote },
];

const checkoutSchema = z.object({
  name: z.string().trim().min(2, "Enter your full name"),
  email: z.email("Enter a valid email"),
  phone: z.string().trim().regex(/^[6-9]\d{9}$/, "Enter a 10-digit mobile number"),
  line1: z.string().trim().min(4, "Enter your address"),
  line2: z.string().trim().optional(),
  city: z.string().trim().min(2, "Enter your city"),
  region: z.string().min(1, "Choose a state"),
  pincode: z.string().trim().regex(/^\d{6}$/, "Enter a 6-digit pincode"),
});

type CheckoutForm = z.infer<typeof checkoutSchema>;

const EMPTY: CheckoutForm = { name: "", email: "", phone: "", line1: "", line2: "", city: "", region: "", pincode: "" };

type StripeStage = {
  clientSecret: string;
  publishableKey: string;
  order: ShopOrder;
};

type StripeFormProps = {
  orderId: string;
  publishableKey: string;
  clientSecret: string;
  amountLabel: string;
  onDone: (order: ShopOrder) => void;
  onFail: (message: string) => void;
};

/** Readable message from an ApiError/Error without leaking internals. */
function readableError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error && typeof (error as Error).message === "string") {
    return (error as Error).message;
  }
  return "Something went wrong. Please try again.";
}

export function CheckoutPage() {
  const { lines, clearCart, total } = useShop();
  const navigate = useNavigate();
  const [form, setForm] = useState<CheckoutForm>(EMPTY);
  const [payment, setPayment] = useState("upi");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [placing, setPlacing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [stripeStage, setStripeStage] = useState<StripeStage | null>(null);
  const [StripeForm, setStripeForm] = useState<ComponentType<StripeFormProps> | null>(null);

  // Which gateway currently serves each method (server is authoritative).
  const methods = useQuery(paymentMethodsQueryOptions());
  const serverMethod = useMemo(
    () => (methods.data ?? []).find((method) => method.code === payment) ?? null,
    [methods.data, payment],
  );
  const inTestMode = serverMethod?.mode === "test";

  const set = (key: keyof CheckoutForm) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  function finish(order: ShopOrder) {
    clearCart();
    void navigate({
      to: "/order-success",
      search: { order: order.doc_number, total: order.total },
    });
  }

  /** Run the active provider's flow for an order the API just created. */
  async function runPayment(order: ShopOrder) {
    const shopPayment = order.payment;
    if (!shopPayment || !shopPayment.client_payload) {
      // Cash on delivery (or already settled): nothing to collect.
      finish(order);
      return;
    }
    const payload = shopPayment.client_payload;

    if (shopPayment.provider === "razorpay") {
      let result;
      try {
        result = await openRazorpay({
          key: String(payload.key ?? ""),
          order_id: String(payload.order_id ?? ""),
          amount: Number(payload.amount ?? 0),
          currency: String(payload.currency ?? "INR"),
          prefill: { name: form.name, email: form.email, contact: form.phone },
        });
      } catch (error) {
        setPaymentError(readableError(error));
        setPlacing(false);
        return;
      }
      if (!result) {
        setPaymentError(
          `Payment cancelled — order ${order.doc_number} is still pending. "Continue purchase" from your orders to retry.`,
        );
        setPlacing(false);
        return;
      }
      try {
        const confirmed = await confirmPayment(order.id, {
          razorpay_order_id: result.razorpay_order_id,
          razorpay_payment_id: result.razorpay_payment_id,
          razorpay_signature: result.razorpay_signature,
        });
        finish(confirmed);
      } catch (error) {
        setPaymentError(readableError(error));
        setPlacing(false);
      }
      return;
    }

    if (shopPayment.provider === "stripe") {
      // Lazy-load the PaymentElement only when Stripe actually handles payment.
      try {
        const module = await import("./StripePaymentForm");
        setStripeForm(() => module.StripePaymentForm);
        setStripeStage({
          clientSecret: String(payload.client_secret ?? ""),
          publishableKey: String(payload.publishable_key ?? ""),
          order,
        });
        setPlacing(false);
      } catch (error) {
        setPaymentError(readableError(error));
        setPlacing(false);
      }
      return;
    }

    // mock gateway (dev/test): confirm straight away — the API verifies it.
    try {
      const confirmed = await confirmPayment(order.id, { payment_id: "mock_payment" });
      finish(confirmed);
    } catch (error) {
      setPaymentError(readableError(error));
      setPlacing(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = checkoutSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    setPaymentError(null);
    setPlacing(true);
    try {
      const order = await placeOrder(
        {
          name: form.name,
          email: form.email,
          phone: form.phone,
          address: {
            line1: form.line1,
            line2: form.line2,
            city: form.city,
            region: form.region,
            pincode: form.pincode,
            country: "IN",
          },
          payment_method: payment,
        },
        `checkout-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      );
      await runPayment(order);
    } catch (error) {
      setPaymentError(readableError(error));
      setPlacing(false);
    }
  }

  if (lines.length === 0) {
    return (
      <div className="shop-container section">
        <EmptyState
          icon={<ShoppingBag aria-hidden />}
          title="Nothing to check out"
          text="Your bag is empty. Add a few things you love first."
          action={<Link to="/shop" className="btn-primary">Browse products</Link>}
        />
      </div>
    );
  }

  const field = (key: keyof CheckoutForm, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className={`form-field ${errors[key] ? "has-error" : ""}`}>
      <span>{label}</span>
      <input value={form[key] ?? ""} onChange={(event) => set(key)(event.target.value)} {...props} />
      {errors[key] ? <small className="field-error">{errors[key]}</small> : null}
    </label>
  );

  return (
    <>
      <PageHero title="Checkout" text="Guest checkout — no account needed." />
      <form className="shop-container section checkout-grid" onSubmit={submit} noValidate>
        <div className="checkout-form">
          <section className="form-card fade-up">
            <h3><span className="step">1</span> Contact</h3>
            <div className="form-cols">
              {field("name", "Full name", { autoComplete: "name" })}
              {field("email", "Email", { type: "email", autoComplete: "email" })}
              {field("phone", "Mobile number", { inputMode: "numeric", autoComplete: "tel", maxLength: 10 })}
            </div>
          </section>

          <section className="form-card fade-up delay-1">
            <h3><span className="step">2</span> Delivery address</h3>
            {field("line1", "Address line 1", { autoComplete: "address-line1" })}
            {field("line2", "Address line 2 (optional)", { autoComplete: "address-line2" })}
            <div className="form-cols">
              {field("city", "City", { autoComplete: "address-level2" })}
              <div className={`form-field ${errors.region ? "has-error" : ""}`}>
                <span>State</span>
                <SheetSelect
                  value={form.region}
                  options={STATES}
                  onChange={set("region")}
                  placeholder="Choose state"
                  title="Choose state"
                  searchPlaceholder="Search states…"
                />
                {errors.region ? <small className="field-error">{errors.region}</small> : null}
              </div>
              {field("pincode", "Pincode", { inputMode: "numeric", autoComplete: "postal-code", maxLength: 6 })}
            </div>
          </section>

          <section className="form-card fade-up delay-2">
            <h3><span className="step">3</span> Payment</h3>
            <div className="pay-options" role="radiogroup" aria-label="Payment method">
              {PAYMENT_METHODS.map((method) => {
                const server = (methods.data ?? []).find((m) => m.code === method.code);
                // With the gateway config loaded, only offer what the store can
                // actually take (COD additionally depends on the pincode zone).
                if (methods.data && server && !server.available) return null;
                return (
                  <label key={method.code} className={`pay-option ${payment === method.code ? "active" : ""}`}>
                    <input type="radio" name="payment" value={method.code} checked={payment === method.code} onChange={() => setPayment(method.code)} />
                    <method.icon aria-hidden />
                    <span>
                      <strong>{method.label}</strong>
                      <small>{method.hint}</small>
                    </span>
                  </label>
                );
              })}
            </div>

            {inTestMode ? (
              <p style={{ margin: "10px 0 0" }}>
                <Badge tone="warn">TEST MODE</Badge>{" "}
                <span className="fine-print">Test payment — no real money moves.</span>
              </p>
            ) : null}

            {paymentError ? <ErrorBanner error={new Error(paymentError)} /> : null}

            {stripeStage && StripeForm ? (
              <div className="form-card" style={{ marginTop: 14 }}>
                <h3>Card details</h3>
                <StripeForm
                  orderId={stripeStage.order.id}
                  publishableKey={stripeStage.publishableKey}
                  clientSecret={stripeStage.clientSecret}
                  amountLabel={money(total)}
                  onDone={finish}
                  onFail={(message) => {
                    setStripeStage(null);
                    setPaymentError(
                      `${message} Order ${stripeStage.order.doc_number} is still pending — place the order again to retry.`,
                    );
                  }}
                />
              </div>
            ) : null}
          </section>
        </div>

        <OrderSummary>
          <ul className="summary-lines">
            {lines.map((line) => (
              <li key={line.productId}>
                <span className="summary-thumb">
                  <ImagePlaceholder tone={line.product.tone} src={productImage(line.productId)} />
                  <span className="qty-badge">{line.qty}</span>
                </span>
                <span className="summary-name">{line.product.name}</span>
                <span>{money(line.lineTotal)}</span>
              </li>
            ))}
          </ul>
          <button
            type="submit"
            className="btn-primary block"
            disabled={placing || stripeStage !== null}
          >
            {placing ? <span className="spinner" aria-hidden /> : <Lock aria-hidden />}
            {placing ? "Placing order…" : stripeStage ? "Complete payment above" : `Place order · ${money(total)}`}
          </button>
          <p className="fine-print">By placing your order you agree to our <Link to="/policies/$slug" params={{ slug: "terms" }}>terms</Link>.</p>
        </OrderSummary>
      </form>
    </>
  );
}
