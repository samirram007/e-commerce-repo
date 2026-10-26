import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Banknote, CreditCard, Landmark, Lock, ShoppingBag, Smartphone } from "lucide-react";
import { z } from "zod";
import { SheetSelect } from "../../components/sheet";
import { fieldErrors } from "../../lib/zod-utils";
import { EmptyState, ImagePlaceholder, money, PageHero } from "./components";
import { productImage } from "./demo-catalog";
import { OrderSummary } from "./CartPage";
import { useShop } from "./shop-state";

const STATES = [
  "Andhra Pradesh", "Assam", "Bihar", "Delhi", "Goa", "Gujarat", "Haryana", "Karnataka", "Kerala",
  "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
  "Uttar Pradesh", "Uttarakhand", "West Bengal",
].map((name) => ({ value: name, label: name }));

const PAYMENT_METHODS = [
  { code: "upi", label: "UPI", hint: "GPay, PhonePe, Paytm", icon: Smartphone },
  { code: "card", label: "Credit / Debit card", hint: "Visa, Mastercard, RuPay", icon: CreditCard },
  { code: "netbanking", label: "Net banking", hint: "All major banks", icon: Landmark },
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

export function CheckoutPage() {
  const { lines, clearCart, total } = useShop();
  const navigate = useNavigate();
  const [form, setForm] = useState<CheckoutForm>(EMPTY);
  const [payment, setPayment] = useState("upi");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [placing, setPlacing] = useState(false);

  const set = (key: keyof CheckoutForm) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = checkoutSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    setPlacing(true);
    // Demo checkout: no public storefront order API exists yet, so simulate placing the order.
    window.setTimeout(() => {
      const orderNumber = `SO-${Date.now().toString().slice(-6)}`;
      clearCart();
      void navigate({ to: "/order-success", search: { order: orderNumber, total: total.toFixed(2) } });
    }, 900);
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
              {PAYMENT_METHODS.map((method) => (
                <label key={method.code} className={`pay-option ${payment === method.code ? "active" : ""}`}>
                  <input type="radio" name="payment" value={method.code} checked={payment === method.code} onChange={() => setPayment(method.code)} />
                  <method.icon aria-hidden />
                  <span>
                    <strong>{method.label}</strong>
                    <small>{method.hint}</small>
                  </span>
                </label>
              ))}
            </div>
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
          <button type="submit" className="btn-primary block" disabled={placing}>
            {placing ? <span className="spinner" aria-hidden /> : <Lock aria-hidden />}
            {placing ? "Placing order…" : `Place order · ${money(total)}`}
          </button>
          <p className="fine-print">By placing your order you agree to our <Link to="/policies/$slug" params={{ slug: "terms" }}>terms</Link>.</p>
        </OrderSummary>
      </form>
    </>
  );
}
