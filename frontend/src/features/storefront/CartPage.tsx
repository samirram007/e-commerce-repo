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
  );
}

export function CartPage() {
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
  );
}
