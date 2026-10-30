import { useEffect, useState, type ComponentType } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { applyCoupon, placeOrder, removeCoupon } from "./api";
import { completePayment, type PaymentOutcome } from "./payment-flow";
import type { StripePaymentFormProps } from "./StripePaymentForm";
import type { ShopOrder } from "./types";
import {
  cartQueryOptions,
  isValidPincode,
  paymentMethodsQueryOptions,
  pincodeQueryOptions,
  shippingOptionsQueryOptions,
  shopKeys,
} from "./queries";
import { Badge, Button, EmptyState, Field, Input, Spinner } from "../../components/ui";
import { formatMoney, gstLabel } from "../../lib/format";
import { useStoreCurrency } from "./store-context";

function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `id_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

export function CheckoutPage() {
  const qc = useQueryClient();
  const currency = useStoreCurrency();
  const cart = useQuery(cartQueryOptions());

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [region, setRegion] = useState("");
  const [pincode, setPincode] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [shippingCode, setShippingCode] = useState("");
  const [promoCode, setPromoCode] = useState("");
  const [done, setDone] = useState<{
    orderId: string;
    docNumber: string;
    total: string;
    paymentState: string;
    method: string;
  } | null>(null);
  // Stripe finishes in its PaymentElement, lazy-loaded only when needed.
  const [stripeStage, setStripeStage] = useState<Extract<PaymentOutcome, { kind: "stripe" }> | null>(null);
  const [StripeForm, setStripeForm] = useState<ComponentType<StripePaymentFormProps> | null>(null);
  const [stripeError, setStripeError] = useState<string | null>(null);

  const pinOk = isValidPincode(pincode);
  const pincodeQuery = useQuery(pincodeQueryOptions(pincode));
  const paymentMethods = useQuery(paymentMethodsQueryOptions(pinOk ? pincode.trim() : undefined));
  const shippingOptions = useQuery(
    shippingOptionsQueryOptions(pinOk ? pincode.trim() : undefined),
  );

  const shipOptions = shippingOptions.data ?? [];
  const selectedShipping = shipOptions.find((option) => option.code === shippingCode) ?? shipOptions[0];

  const codAllowed = pincodeQuery.data?.cod_allowed ?? true;
  const pmOptions = (paymentMethods.data ?? []).filter(
    (m) => m.available && (m.code !== "cod" || codAllowed),
  );
  // The server resolves which gateway (Razorpay / Stripe / mock) serves each
  // method, and in which credential mode.
  const selectedMethod = pmOptions.find((m) => m.code === paymentMethod);
  const onlinePayment = Boolean(selectedMethod && selectedMethod.code !== "cod");

  // Preselect the first usable method so "Pay" opens the gateway straight away.
  useEffect(() => {
    if (paymentMethod || pmOptions.length === 0) return;
    setPaymentMethod(pmOptions[0]?.code ?? "");
  }, [paymentMethod, pmOptions]);

  // The shop's delivery options can change with the PIN code / cart; keep one selected.
  useEffect(() => {
    if (shippingCode && shipOptions.some((option) => option.code === shippingCode)) return;
    setShippingCode(shipOptions[0]?.code ?? "");
  }, [shippingCode, shipOptions]);

  // A PIN-code change can withdraw COD; fall back to a method that is still offered.
  useEffect(() => {
    if (!paymentMethod) return;
    if (pmOptions.some((m) => m.code === paymentMethod)) return;
    setPaymentMethod(pmOptions[0]?.code ?? "");
  }, [paymentMethod, pmOptions]);

  // Promo code: the backend prices it, so the quote below is always the truth.
  const applyPromo = useMutation({
    mutationFn: (code: string) => applyCoupon(code),
    onSuccess: () => {
      setPromoCode("");
      qc.invalidateQueries({ queryKey: shopKeys.cart });
    },
  });
  const dropPromo = useMutation({
    mutationFn: () => removeCoupon(),
    onSuccess: () => qc.invalidateQueries({ queryKey: shopKeys.cart }),
  });

  function finish(order: ShopOrder) {
    setStripeStage(null);
    qc.invalidateQueries({ queryKey: shopKeys.cart });
    qc.invalidateQueries({ queryKey: shopKeys.orders });
    setDone({
      orderId: order.id,
      docNumber: order.doc_number,
      total: order.total,
      paymentState: order.payment_state,
      method: paymentMethod,
    });
  }

  const place = useMutation({
    mutationFn: async (): Promise<PaymentOutcome> => {
      setStripeError(null);
      const order = await placeOrder(
        {
          name,
          email,
          phone: phone || undefined,
          address: {
            line1,
            line2: line2 || undefined,
            city: city || undefined,
            region: region || undefined,
            pincode: pincode.trim() || undefined,
            country: "IN",
          },
          payment_method: paymentMethod,
          shipping_total: cart.data?.quote.shipping_total,
          // Only carriers the shop configured are sent; standard delivery omits it.
          ...(selectedShipping?.carrier ? { shipping_carrier: selectedShipping.carrier } : {}),
        },
        uuid(),
      );
      let outcome: PaymentOutcome;
      try {
        outcome = await completePayment(order, { name, email, contact: phone || undefined });
      } catch (cause) {
        throw new Error(
          `Payment not completed (${(cause as Error).message}). Order ${order.doc_number} is saved — pay it from Orders.`,
        );
      }
      if (outcome.kind === "cancelled") {
        qc.invalidateQueries({ queryKey: shopKeys.orders });
        throw new Error(
          `Payment cancelled — order ${order.doc_number} is still pending. Pay it from your orders to retry.`,
        );
      }
      if (outcome.kind === "stripe") {
        const module = await import("./StripePaymentForm");
        setStripeForm(() => module.StripePaymentForm);
      }
      return outcome;
    },
    onSuccess: (outcome) => {
      if (outcome.kind === "stripe") {
        setStripeStage(outcome);
        return;
      }
      finish(outcome.order);
    },
  });

  if (done) {
    return (
      <div className="shop-page">
        <h1 className="page-title">
          {done.paymentState === "paid"
            ? "Order placed"
            : done.paymentState === "refunded"
              ? "Payment refunded"
              : done.method === "cod"
                ? "Order confirmed · pay on delivery"
                : "Order placed · payment pending"}
        </h1>
        <div className="card shop-order-card">
          <p>
            Thank you! Your order <strong>{done.docNumber}</strong> has been placed.
          </p>
          <p className="muted">Total: {formatMoney(done.total, currency)}</p>
          {done.paymentState === "refunded" ? (
            <p className="muted">
              This order expired before the payment finished, so the full amount was refunded to
              your original payment method.
            </p>
          ) : done.paymentState !== "paid" ? (
            <p className="muted">
              {done.method === "cod"
                ? "You will pay cash when the order is delivered."
                : "Complete the payment from your orders page — the order is reserved until then."}
            </p>
          ) : null}
          <div className="shop-cart-actions">
            <Link to="/shop/orders" className="btn">
              View orders
            </Link>
            <Link to="/shop" className="btn secondary">
              Continue shopping
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (cart.isLoading) return <Spinner />;
  if (cart.isError) return <EmptyState title="Could not load your cart" message={(cart.error as Error).message} />;
  if (!cart.data || cart.data.items.length === 0) {
    return (
      <div className="shop-page">
        <h1 className="page-title">Checkout</h1>
        <EmptyState title="Your cart is empty" message="Add a product before checking out." />
        <div className="shop-cart-empty-cta">
          <Link to="/shop" className="btn">
            Browse products
          </Link>
        </div>
      </div>
    );
  }

  const quote = cart.data.quote;
  const deliverable = pincodeQuery.data?.deliverable ?? true;

  return (
    <div className="shop-page">
      <div className="shop-results-head">
        <h1 className="page-title">Checkout</h1>
        <Link to="/cart" className="shop-text-link">
          Back to cart
        </Link>
      </div>

      <div className="shop-checkout">
        <div className="shop-checkout-form">
          <h2>Contact</h2>
          <Field label="Full name">
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Phone">
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>

          <h2>Shipping address</h2>
          <Field label="Address line 1">
            <Input value={line1} onChange={(e) => setLine1(e.target.value)} required />
          </Field>
          <Field label="Address line 2">
            <Input value={line2} onChange={(e) => setLine2(e.target.value)} />
          </Field>
          <div className="shop-form-row">
            <Field label="City">
              <Input value={city} onChange={(e) => setCity(e.target.value)} />
            </Field>
            <Field label="State">
              <Input
                value={region || pincodeQuery.data?.state || ""}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="From PIN code"
              />
            </Field>
          </div>
          <Field label="PIN code">
            <Input
              value={pincode}
              onChange={(e) => setPincode(e.target.value)}
              placeholder="6-digit PIN code"
              inputMode="numeric"
              maxLength={6}
            />
          </Field>
          {pincode.trim().length > 0 && !pinOk ? (
            <p className="shop-hint">Enter a 6-digit Indian PIN code (it cannot start with 0).</p>
          ) : null}
          {pinOk ? (
            pincodeQuery.isLoading ? (
              <Spinner />
            ) : pincodeQuery.isError ? (
              <p className="error-text">{(pincodeQuery.error as Error).message}</p>
            ) : pincodeQuery.data ? (
              <div className="shop-pincode-result">
                {pincodeQuery.data.deliverable ? (
                  <span className="badge ok">
                    {[pincodeQuery.data.city, pincodeQuery.data.state].filter(Boolean).join(", ") || "Deliverable"}
                    {" · ETA "}
                    {pincodeQuery.data.eta_days ?? "?"} days
                    {pincodeQuery.data.cod_allowed ? " · COD available" : ""}
                  </span>
                ) : (
                  <span className="badge bad">
                    {pincodeQuery.data.configured
                      ? `We do not deliver to ${pincodeQuery.data.pincode}`
                      : `${pincodeQuery.data.state ?? "This area"} is not in our delivery zone yet`}
                  </span>
                )}
              </div>
            ) : null
          ) : null}

          <h2>Delivery</h2>
          {shippingOptions.isLoading ? (
            <Spinner />
          ) : shipOptions.length === 0 ? (
            <p className="shop-hint">Delivery options load once you enter a PIN code.</p>
          ) : (
            <div className="shop-payment-methods">
              {shipOptions.map((option) => (
                <label
                  key={option.code}
                  className={`shop-payment-option ${selectedShipping?.code === option.code ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="shipping_option"
                    value={option.code}
                    checked={selectedShipping?.code === option.code}
                    onChange={() => setShippingCode(option.code)}
                  />
                  <span>{option.label}</span>
                  <span className="muted">
                    {Number(option.price) > 0 ? formatMoney(option.price, currency) : "Free"}
                  </span>
                </label>
              ))}
            </div>
          )}

          <h2>Payment method</h2>
          {paymentMethods.isLoading ? (
            <Spinner />
          ) : pmOptions.length === 0 ? (
            <EmptyState title="No payment methods available" />
          ) : (
            <div className="shop-payment-methods">
              {pmOptions.map((m) => (
                <label key={m.code} className={`shop-payment-option ${paymentMethod === m.code ? "selected" : ""}`}>
                  <input
                    type="radio"
                    name="payment_method"
                    value={m.code}
                    checked={paymentMethod === m.code}
                    onChange={() => setPaymentMethod(m.code)}
                  />
                  <span>{m.label}</span>
                  <span className="muted">{m.code === "cod" ? "offline" : m.provider}</span>
                </label>
              ))}
            </div>
          )}

          {selectedMethod?.mode === "test" && onlinePayment ? (
            <p className="shop-hint">
              <Badge tone="warn">TEST MODE</Badge> Test payment — no real money moves.
            </p>
          ) : null}
          {import.meta.env.DEV && selectedMethod?.provider === "mock" ? (
            <p className="shop-hint">
              No payment gateway is configured, so cards/UPI run on the offline mock gateway.
              Configure Razorpay or Stripe in Settings → Payment gateways.
            </p>
          ) : null}

          {place.isError ? <p className="error-text">{(place.error as Error).message}</p> : null}
          {stripeError ? <p className="error-text">{stripeError}</p> : null}

          {stripeStage && StripeForm ? (
            <div className="card shop-order-card">
              <h2>Card details</h2>
              <StripeForm
                orderId={stripeStage.order.id}
                publishableKey={stripeStage.publishableKey}
                clientSecret={stripeStage.clientSecret}
                amountLabel={formatMoney(stripeStage.order.total, currency)}
                onDone={finish}
                onFail={(message) => {
                  setStripeStage(null);
                  place.reset();
                  qc.invalidateQueries({ queryKey: shopKeys.orders });
                  setStripeError(
                    `${message} Order ${stripeStage.order.doc_number} is still pending — pay it from your orders to retry.`,
                  );
                }}
              />
            </div>
          ) : null}

          <Button
            onClick={() => place.mutate()}
            disabled={
              place.isPending ||
              stripeStage !== null ||
              !name ||
              !email ||
              !line1 ||
              !paymentMethod ||
              !pinOk ||
              !deliverable
            }
          >
            {place.isPending
              ? onlinePayment
                ? "Waiting for payment…"
                : "Placing order…"
              : stripeStage
                ? "Complete payment above"
                : onlinePayment
                  ? `Pay ${formatMoney(quote.total, currency)} · ${selectedMethod?.label ?? "Online"}`
                  : `Place order · ${formatMoney(quote.total, currency)}`}
          </Button>
        </div>

        <aside className="shop-checkout-summary">
          <h2>Order summary</h2>
          <div className="shop-promo">
            {quote.coupon?.valid ? (
              <div className="shop-promo-applied">
                <span>
                  <span className="badge ok">{quote.coupon.code}</span>{" "}
                  {quote.coupon.description ?? "Promo code applied"}
                </span>
                <button
                  type="button"
                  className="shop-text-link"
                  onClick={() => dropPromo.mutate()}
                  disabled={dropPromo.isPending}
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="shop-promo-form">
                <Input
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                  placeholder="Promo code"
                  aria-label="Promo code"
                />
                <Button
                  variant="secondary"
                  onClick={() => applyPromo.mutate(promoCode.trim())}
                  disabled={!promoCode.trim() || applyPromo.isPending}
                >
                  {applyPromo.isPending ? "Checking…" : "Apply"}
                </Button>
              </div>
            )}
            {applyPromo.isError ? (
              <p className="error-text">{(applyPromo.error as Error).message}</p>
            ) : null}
            {quote.coupon && !quote.coupon.valid && quote.coupon.message ? (
              <p className="shop-hint">{quote.coupon.message}</p>
            ) : null}
          </div>
          <div className="shop-summary-items">
            {cart.data.items.map((item) => (
              <div key={item.id} className="shop-summary-item">
                <span>
                  {item.name}
                  <span className="muted"> × {Number(item.qty)}</span>
                </span>
                <span>{formatMoney(item.line_total, currency)}</span>
              </div>
            ))}
          </div>
          <div className="shop-cart-totals">
            <div>
              <span className="muted">Subtotal</span>
              <span>{formatMoney(quote.subtotal, currency)}</span>
            </div>
            {(quote.tax_breakup ?? []).length > 0 ? (
              (quote.tax_breakup ?? []).map((row) => (
                <div key={row.rate}>
                  <span className="muted">{gstLabel(row.rate)}</span>
                  <span>{formatMoney(row.amount, currency)}</span>
                </div>
              ))
            ) : (
              <div>
                <span className="muted">Tax</span>
                <span>{formatMoney(quote.tax_total, currency)}</span>
              </div>
            )}
            {Number(quote.discount_total) > 0 ? (
              <div>
                <span className="muted">
                  Discount{quote.coupon?.code ? ` · ${quote.coupon.code}` : ""}
                </span>
                <span>-{formatMoney(quote.discount_total, currency)}</span>
              </div>
            ) : null}
            <div>
              <span className="muted">
                Shipping{selectedShipping ? ` · ${selectedShipping.label}` : ""}
              </span>
              <span>
                {Number(selectedShipping?.price ?? quote.shipping_total) > 0
                  ? formatMoney(selectedShipping?.price ?? quote.shipping_total, currency)
                  : "Free"}
              </span>
            </div>
            <div className="shop-cart-total">
              <span>Total</span>
              <span>{formatMoney(quote.total, currency)}</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
