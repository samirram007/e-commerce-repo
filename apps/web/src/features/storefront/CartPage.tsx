import { useEffect, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clearCart, removeCartItem, updateCartItem } from "./api";
import { cartQueryOptions, shopKeys } from "./queries";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { formatMoney, gstLabel } from "../../lib/format";
import { useStoreCurrency } from "./store-context";
import { ProductImage } from "./ProductImage";
import type { ShopCartItem } from "./types";

function CartRow({
  item,
  currency,
  busy,
  onQty,
  onRemove,
}: {
  item: ShopCartItem;
  currency: string;
  busy: boolean;
  onQty: (id: string, qty: string) => void;
  onRemove: (id: string) => void;
}) {
  // Quantities arrive as fixed-point strings ("2.0000"); show them plainly.
  const displayQty = String(Number(item.qty) || 1);
  const [draft, setDraft] = useState(displayQty);

  // Keep the input in sync when the server re-prices / normalises the quantity.
  useEffect(() => setDraft(String(Number(item.qty) || 1)), [item.qty]);

  const current = Number(item.qty) || 0;
  const step = (delta: number) => {
    const next = Math.max(1, Math.round(current + delta));
    if (next !== current) onQty(item.id, String(next));
  };
  const commit = () => {
    const next = Number(draft);
    if (!Number.isFinite(next) || next <= 0) {
      onRemove(item.id);
      return;
    }
    if (next === current) return;
    onQty(item.id, String(next));
  };

  return (
    <div className="shop-cart-row">
      <Link to="/shop/$productId" params={{ productId: item.product_id }} className="shop-cart-media">
        <ProductImage name={item.name} sku={item.sku} imageUrl={item.image_url} />
      </Link>

      <div className="shop-cart-info">
        <Link to="/shop/$productId" params={{ productId: item.product_id }} className="shop-cart-name">
          {item.name}
        </Link>
        <span className="muted">
          {item.sku} · {formatMoney(item.unit_price, currency)} each
        </span>
      </div>

      <div className="shop-cart-qty">
        <button type="button" className="shop-qty-step" onClick={() => step(-1)} disabled={busy || current <= 1} aria-label="Decrease quantity">
          −
        </button>
        <input
          type="number"
          min="1"
          inputMode="numeric"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.currentTarget.blur();
            }
          }}
          className="shop-qty-input"
          disabled={busy}
          aria-label={`Quantity for ${item.name}`}
        />
        <button type="button" className="shop-qty-step" onClick={() => step(1)} disabled={busy} aria-label="Increase quantity">
          +
        </button>
      </div>

      <div className="shop-cart-line">
        {formatMoney(item.line_total, currency)}
        <span className="muted shop-cart-line-note">incl. tax</span>
      </div>

      <button
        type="button"
        className="shop-icon-btn danger"
        onClick={() => onRemove(item.id)}
        disabled={busy}
      >
        Remove
      </button>
    </div>
  );
}

export function CartPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const currency = useStoreCurrency();
  const cart = useQuery(cartQueryOptions());
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: shopKeys.cart });

  const update = useMutation({
    mutationFn: ({ id, qty }: { id: string; qty: string }) => updateCartItem(id, qty),
    onMutate: ({ id }) => setBusy(id),
    onSettled: () => {
      setBusy(null);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => removeCartItem(id),
    onMutate: (id) => setBusy(id),
    onSettled: () => {
      setBusy(null);
      refresh();
    },
  });
  const clear = useMutation({
    mutationFn: () => clearCart(),
    onSettled: () => refresh(),
  });

  if (cart.isLoading) return <Spinner />;
  if (cart.isError) return <EmptyState title="Could not load cart" message={(cart.error as Error).message} />;
  const data = cart.data!;
  const items = data.items ?? [];

  if (items.length === 0) {
    return (
      <div className="shop-page">
        <h1 className="page-title">Your cart</h1>
        <EmptyState title="Your cart is empty" message="Add some products to get started." />
        <div className="shop-cart-empty-cta">
          <Link to="/shop" className="btn">
            Browse products
          </Link>
        </div>
      </div>
    );
  }

  const mutationError = update.error ?? remove.error ?? clear.error;

  return (
    <div className="shop-page">
      <div className="shop-results-head">
        <h1 className="page-title">Your cart</h1>
        <div className="shop-results-meta">
          <span className="muted">
            {items.length} item{items.length === 1 ? "" : "s"}
          </span>
          <Link to="/shop" className="shop-text-link">
            Continue shopping
          </Link>
        </div>
      </div>

      {mutationError ? (
        <p className="error-text">{(mutationError as Error).message}</p>
      ) : null}

      <div className="shop-cart-list">
        {items.map((item) => (
          <CartRow
            key={item.id}
            item={item}
            currency={currency}
            busy={busy === item.id}
            onQty={(id, qty) => update.mutate({ id, qty })}
            onRemove={(id) => remove.mutate(id)}
          />
        ))}
      </div>

      <div className="shop-cart-summary">
        <div className="shop-cart-totals">
          <div>
            <span className="muted">Subtotal</span>
            <span>{formatMoney(data.quote.subtotal, currency)}</span>
          </div>
          {Number(data.quote.discount_total) > 0 ? (
            <div>
              <span className="muted">Discount</span>
              <span>-{formatMoney(data.quote.discount_total, currency)}</span>
            </div>
          ) : null}
          {(data.quote.tax_breakup ?? []).length > 0 ? (
            (data.quote.tax_breakup ?? []).map((row) => (
              <div key={row.rate}>
                <span className="muted">{gstLabel(row.rate)}</span>
                <span>{formatMoney(row.amount, currency)}</span>
              </div>
            ))
          ) : (
            <div>
              <span className="muted">Tax</span>
              <span>{formatMoney(data.quote.tax_total, currency)}</span>
            </div>
          )}
          <div>
            <span className="muted">Shipping</span>
            <span>{Number(data.quote.shipping_total) > 0 ? formatMoney(data.quote.shipping_total, currency) : "Free"}</span>
          </div>
          <div className="shop-cart-total">
            <span>Total</span>
            <span>{formatMoney(data.quote.total, currency)}</span>
          </div>
        </div>
        <div className="shop-cart-actions">
          <Button variant="secondary" onClick={() => clear.mutate()} disabled={clear.isPending}>
            {clear.isPending ? "Clearing…" : "Clear cart"}
          </Button>
          <Button onClick={() => navigate({ to: "/checkout" })} disabled={clear.isPending}>
            Checkout
          </Button>
        </div>
      </div>
    </div>
  );
}
