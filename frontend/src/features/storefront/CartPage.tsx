<<<<<<< HEAD
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
      <Link to="/shop/products/$productId" params={{ productId: item.product_id }} className="shop-cart-media">
        <ProductImage name={item.name} sku={item.sku} imageUrl={item.image_url} />
      </Link>

      <div className="shop-cart-info">
        <Link to="/shop/products/$productId" params={{ productId: item.product_id }} className="shop-cart-name">
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
=======
import { Link } from "@tanstack/react-router";
import { ArrowRight, Heart, Minus, Plus, ShoppingBag, Trash2, Truck } from "lucide-react";
import { EmptyState, ImagePlaceholder, money, PageHero, ProductCard, ProductRail, Reveal, SectionHeader } from "./components";
import { FREE_SHIPPING_THRESHOLD, PRODUCTS, productImage } from "./demo-catalog";
import { useShop } from "./shop-state";

export function OrderSummary({ children }: { children?: React.ReactNode }) {
  const { subtotal, shipping, total, cartCount } = useShop();
  return (
    <aside className="summary">
      <h3>Order summary</h3>
      <div className="summary-row"><span>Items ({cartCount})</span><span>{money(subtotal)}</span></div>
      <div className="summary-row"><span>Shipping</span><span>{shipping === 0 ? "Free" : money(shipping)}</span></div>
      <div className="summary-row muted-text"><span>Taxes</span><span>Included</span></div>
      <div className="summary-row total"><span>Total</span><span>{money(total)}</span></div>
      {children}
    </aside>
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
  );
}

export function CartPage() {
<<<<<<< HEAD
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
          <Link to="/shop/products" className="btn">
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
          <Link to="/shop/products" className="shop-text-link">
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
          <Button onClick={() => navigate({ to: "/shop/checkout" })} disabled={clear.isPending}>
            Checkout
          </Button>
        </div>
      </div>
    </div>
=======
  const { lines, subtotal, setQty, removeFromCart, toggleWishlist } = useShop();
  const remaining = Math.max(0, FREE_SHIPPING_THRESHOLD - subtotal);
  const progress = Math.min(100, (subtotal / FREE_SHIPPING_THRESHOLD) * 100);
  const suggestions = PRODUCTS.filter((p) => !lines.some((l) => l.productId === p.id) && p.badge === "Bestseller");

  return (
    <>
      <PageHero title="Your bag" text={lines.length ? "Review your items before checkout." : undefined} />
      <div className="shop-container section">
        {lines.length === 0 ? (
          <>
            <EmptyState
              icon={<ShoppingBag aria-hidden />}
              title="Your bag is empty"
              text="Looks like you haven't added anything yet. Let's fix that."
              action={<Link to="/shop" className="btn-primary">Start shopping <ArrowRight aria-hidden /></Link>}
            />
            <section className="section">
              <SectionHeader eyebrow="Popular right now" title="Bestsellers" />
              <ProductRail products={PRODUCTS.filter((p) => p.badge === "Bestseller")} />
            </section>
          </>
        ) : (
          <div className="checkout-grid">
            <div>
              <Reveal className="ship-progress">
                <Truck aria-hidden />
                <div>
                  <span>
                    {remaining > 0 ? <>Add <strong>{money(remaining)}</strong> more for free shipping</> : <strong>You've unlocked free shipping!</strong>}
                  </span>
                  <div className="progress"><span style={{ width: `${progress}%` }} /></div>
                </div>
              </Reveal>
              <ul className="cart-lines">
                {lines.map((line, i) => (
                  <Reveal as="li" key={line.productId} delay={i * 60} className="cart-line">
                    <Link to="/shop/$productId" params={{ productId: line.productId }} className="cart-thumb">
                      <ImagePlaceholder tone={line.product.tone} src={productImage(line.productId)} />
                    </Link>
                    <div className="cart-info">
                      <Link to="/shop/$productId" params={{ productId: line.productId }} className="product-name">{line.product.name}</Link>
                      <span className="muted-text">SKU {line.product.sku} · {money(line.product.price)} each</span>
                      <div className="cart-line-actions">
                        <div className="stepper small">
                          <button type="button" onClick={() => setQty(line.productId, line.qty - 1)} aria-label="Decrease quantity"><Minus aria-hidden /></button>
                          <span>{line.qty}</span>
                          <button type="button" onClick={() => setQty(line.productId, line.qty + 1)} aria-label="Increase quantity"><Plus aria-hidden /></button>
                        </div>
                        <button
                          type="button"
                          className="link-btn"
                          onClick={() => {
                            toggleWishlist(line.productId);
                            removeFromCart(line.productId);
                          }}
                        >
                          <Heart aria-hidden /> Save for later
                        </button>
                        <button type="button" className="link-btn danger" onClick={() => removeFromCart(line.productId)}>
                          <Trash2 aria-hidden /> Remove
                        </button>
                      </div>
                    </div>
                    <strong className="cart-total">{money(line.lineTotal)}</strong>
                  </Reveal>
                ))}
              </ul>
            </div>
            <OrderSummary>
              <Link to="/checkout" className="btn-primary block">Checkout <ArrowRight aria-hidden /></Link>
              <Link to="/shop" className="btn-ghost block">Continue shopping</Link>
            </OrderSummary>
          </div>
        )}
        {lines.length > 0 && suggestions.length > 0 ? (
          <section className="section">
            <SectionHeader eyebrow="Complete the look" title="Frequently bought together" />
            <div className="product-grid">
              {suggestions.slice(0, 4).map((p) => <ProductCard key={p.id} product={p} />)}
            </div>
          </section>
        ) : null}
      </div>
    </>
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
  );
}
