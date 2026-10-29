/**
 * Stripe checkout form (PaymentElement).
 *
 * This module is imported lazily — only when the store's active gateway is
 * Stripe — so `@stripe/react-stripe-js` never loads otherwise. The shopper
 * confirms in the element; the result is then POSTed to /payment/confirm,
 * where the API re-verifies the PaymentIntent server-side.
 */
import { useState } from "react";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import { Button, ErrorBanner } from "../../components/ui";
import { confirmPayment, type PaymentConfirmPayload } from "./api";

export interface StripePaymentFormProps {
  orderId: string;
  publishableKey: string;
  clientSecret: string;
  amountLabel: string;
  /** Called with the finalized order once the API confirms it. */
  onDone: (order: Awaited<ReturnType<typeof confirmPayment>>) => void;
  /** Called when the shopper cancels or the payment fails; order stays pending. */
  onFail: (message: string) => void;
}

function StripeInner({ orderId, amountLabel, onDone, onFail }: Omit<StripePaymentFormProps, "publishableKey" | "clientSecret">) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pay() {
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);
    try {
      const { error: failure, paymentIntent } = await stripe.confirmPayment({
        elements,
        redirect: "if_required",
        confirmParams: { return_url: window.location.href },
      });
      if (failure || !paymentIntent) {
        const message = failure?.message ?? "The payment could not be completed.";
        setError(message);
        setBusy(false);
        onFail(message);
        return;
      }
      const payload: PaymentConfirmPayload = { payment_intent_id: paymentIntent.id };
      const order = await confirmPayment(orderId, payload);
      onDone(order);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Payment failed.";
      setError(message);
      setBusy(false);
      onFail(message);
    }
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <PaymentElement />
      <ErrorBanner error={error ? new Error(error) : null} />
      <Button onClick={() => void pay()} disabled={busy || !stripe || !elements}>
        {busy ? "Processing…" : `Pay ${amountLabel}`}
      </Button>
    </div>
  );
}

/** Lazily-loaded wrapper: creates the Stripe instance and mounts the element. */
export function StripePaymentForm(props: StripePaymentFormProps) {
  const [stripePromise] = useState<Promise<Stripe | null>>(() => loadStripe(props.publishableKey));

  return (
    <Elements
      stripe={stripePromise}
      options={{ clientSecret: props.clientSecret, locale: "auto" }}
    >
      <StripeInner
        orderId={props.orderId}
        amountLabel={props.amountLabel}
        onDone={props.onDone}
        onFail={props.onFail}
      />
    </Elements>
  );
}