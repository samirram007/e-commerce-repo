import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createRazorpayOrder,
  placeOrder,
  verifyRazorpayPayment,
} from "./api";
import { openRazorpayCheckout } from "./razorpay";
import type { ShopOrder } from "./types";
import {
  cartQueryOptions,
  isValidPincode,
  paymentMethodsQueryOptions,
  pincodeQueryOptions,
  shopKeys,
} from "./queries";
import { Button, EmptyState, Field, Input, Spinner } from "../../components/ui";
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
  const [done, setDone] = useState<{
    orderId: string;
    docNumber: string;
    total: string;
    paymentState: string;
    method: string;
  } | null>(null);

  const pinOk = isValidPincode(pincode);
  const pincodeQuery = useQuery(pincodeQueryOptions(pincode));
  const paymentMethods = useQuery(paymentMethodsQueryOptions(pinOk ? pincode.trim() : undefined));

  const codAllowed = pincodeQuery.data?.cod_allowed ?? true;
  const pmOptions = (paymentMethods.data ?? []).filter(
    (m) => m.available && (m.code !== "cod" || codAllowed),
  );
  const gatewayMissing = (paymentMethods.data ?? []).some(
    (m) => m.code === "razorpay" && !m.available,
  );

  // Checkout runs through the gateway: preselect the first usable method
  // (Razorpay when the API has keys) so "Pay" opens Checkout straight away.
  useEffect(() => {
    if (paymentMethod || pmOptions.length === 0) return;
    setPaymentMethod(pmOptions[0]?.code ?? "");
  }, [paymentMethod, pmOptions]);

  // A PIN-code change can withdraw COD; fall back to a method that is still offered.
  useEffect(() => {
    if (!paymentMethod) return;
    if (pmOptions.some((m) => m.code === paymentMethod)) return;
    setPaymentMethod(pmOptions[0]?.code ?? "");
  }, [paymentMethod, pmOptions]);

  const place = useMutation({
    mutationFn: async (): Promise<ShopOrder> => {
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
        },
        uuid(),
      );
      if (order.payment_state === "paid" || paymentMethod !== "razorpay") return order;

      // Razorpay: create the gateway order, open Checkout, verify server-side.
      const intent = await createRazorpayOrder(order.id);
      let verified;
      try {
        verified = await openRazorpayCheckout(intent, { name, email, contact: phone || undefined });
      } catch (cause) {
        throw new Error(
          `Payment not completed (${(cause as Error).message}). Order ${order.doc_number} is saved — pay it from Orders.`,
        );
      }
      return verifyRazorpayPayment(order.id, verified);
    },
    onSuccess: (order) => {
      qc.invalidateQueries({ queryKey: shopKeys.cart });
      qc.invalidateQueries({ queryKey: shopKeys.orders });
      setDone({
        orderId: order.id,
        docNumber: order.doc_number,
        total: order.total,
        paymentState: order.payment_state,
        method: paymentMethod,
      });
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
                  <span className="muted">{m.provider}</span>
                </label>
              ))}
            </div>
          )}

          {import.meta.env.DEV && gatewayMissing ? (
            <p className="shop-hint">
              Razorpay is not configured, so cards/UPI run through the sandbox gateway instead of
              the Razorpay window. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to backend/.env and
              restart the API to take the Checkout popup.
            </p>
          ) : null}

          {place.isError ? <p className="error-text">{(place.error as Error).message}</p> : null}

          <Button
            onClick={() => place.mutate()}
            disabled={
              place.isPending ||
              !name ||
              !email ||
              !line1 ||
              !paymentMethod ||
              !pinOk ||
              !deliverable
            }
          >
            {place.isPending
              ? paymentMethod === "razorpay"
                ? "Waiting for payment…"
                : "Placing order…"
              : paymentMethod === "razorpay"
                ? `Pay ${formatMoney(quote.total, currency)} · Razorpay`
                : `Place order · ${formatMoney(quote.total, currency)}`}
          </Button>
        </div>

        <aside className="shop-checkout-summary">
          <h2>Order summary</h2>
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
            <div>
              <span className="muted">Shipping</span>
              <span>{Number(quote.shipping_total) > 0 ? formatMoney(quote.shipping_total, currency) : "Free"}</span>
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
