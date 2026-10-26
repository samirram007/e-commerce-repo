import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Check, ChevronLeft, ChevronRight, Heart, Minus, PackageX, Plus, RotateCcw, ShieldCheck, Truck } from "lucide-react";
import { EmptyState, ImagePlaceholder, Price, ProductRail, Reveal, SectionHeader, Stars } from "./components";
import { categoryBySlug, productById, productImage, productsIn, PRODUCTS } from "./demo-catalog";
import { useShop } from "./shop-state";

const GALLERY_VIEWS = ["Front", "Side", "Detail", "Lifestyle"];
const TABS = ["Description", "Highlights", "Shipping & returns"] as const;

export function ProductPage({ productId }: { productId: string }) {
  const product = productById(productId);
  const { addToCart, toggleWishlist, isWishlisted } = useShop();
  const [view, setView] = useState(0);
  const [qty, setQty] = useState(1);
  const [color, setColor] = useState(0);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Description");
  const [added, setAdded] = useState(false);

  if (!product) {
    return (
      <div className="shop-container section">
        <EmptyState
          icon={<PackageX aria-hidden />}
          title="Product not found"
          text="It may have sold out or moved. Explore the rest of the store instead."
          action={<Link to="/shop" className="btn-primary">Browse products</Link>}
        />
      </div>
    );
  }

  const category = categoryBySlug(product.category);
  const related = [
    ...productsIn(product.category).filter((p) => p.id !== product.id),
    ...PRODUCTS.filter((p) => p.category !== product.category && p.badge === "Bestseller"),
  ].slice(0, 8);
  const lowStock = product.stock < 15;

  function add() {
    addToCart(product!.id, qty);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1600);
  }

  return (
    <div className="shop-container section">
      <nav className="breadcrumbs fade-up" aria-label="Breadcrumb">
        <Link to="/">Home</Link>
        <span>/</span>
        <Link to="/shop" search={{ category: product.category }}>{category?.name}</Link>
        <span>/</span>
        <span aria-current="page">{product.name}</span>
      </nav>

      <div className="pdp">
        <div className="gallery fade-up">
          <div className="gallery-main">
            <div className="gallery-track" style={{ transform: `translateX(-${view * 100}%)` }}>
              {GALLERY_VIEWS.map((label) => (
                <ImagePlaceholder key={label} tone={product.tone} label={`${label} view`} className="gallery-slide" src={productImage(product.id)} />
              ))}
            </div>
            <button type="button" className="hero-arrow prev" onClick={() => setView((view + GALLERY_VIEWS.length - 1) % GALLERY_VIEWS.length)} aria-label="Previous image">
              <ChevronLeft aria-hidden />
            </button>
            <button type="button" className="hero-arrow next" onClick={() => setView((view + 1) % GALLERY_VIEWS.length)} aria-label="Next image">
              <ChevronRight aria-hidden />
            </button>
            {product.badge ? <span className={`chip chip-${product.badge.toLowerCase()}`}>{product.badge}</span> : null}
          </div>
          <div className="thumbs">
            {GALLERY_VIEWS.map((label, i) => (
              <button key={label} type="button" className={`thumb ${i === view ? "active" : ""}`} onClick={() => setView(i)} aria-label={`Show ${label} view`}>
                <ImagePlaceholder tone={product.tone} src={productImage(product.id)} />
              </button>
            ))}
          </div>
        </div>

        <div className="pdp-info fade-up delay-1">
          <div className="product-cat">{category?.name} · SKU {product.sku}</div>
          <h1>{product.name}</h1>
          <Stars rating={product.rating} reviews={product.reviews} />
          <Price product={product} large />
          <p className="pdp-desc">{product.description}</p>

          <div className="pdp-option">
            <span className="option-label">Colour</span>
            <div className="swatches">
              {product.colors.map((hex, i) => (
                <button
                  key={hex}
                  type="button"
                  className={`swatch ${i === color ? "active" : ""}`}
                  style={{ background: hex }}
                  onClick={() => setColor(i)}
                  aria-label={`Colour ${i + 1}`}
                  aria-pressed={i === color}
                />
              ))}
            </div>
          </div>

          <div className={`stock ${lowStock ? "low" : ""}`}>
            <span className="stock-dot" />
            {lowStock ? `Only ${product.stock} left — order soon` : "In stock, ready to ship"}
          </div>

          <div className="pdp-actions">
            <div className="stepper" aria-label="Quantity">
              <button type="button" onClick={() => setQty(Math.max(1, qty - 1))} aria-label="Decrease quantity"><Minus aria-hidden /></button>
              <span>{qty}</span>
              <button type="button" onClick={() => setQty(Math.min(product.stock, qty + 1))} aria-label="Increase quantity"><Plus aria-hidden /></button>
            </div>
            <button type="button" className={`btn-primary grow ${added ? "success" : ""}`} onClick={add}>
              {added ? <><Check aria-hidden /> Added</> : "Add to bag"}
            </button>
            <button
              type="button"
              className={`icon-btn wish-lg ${isWishlisted(product.id) ? "active" : ""}`}
              onClick={() => toggleWishlist(product.id)}
              aria-label="Toggle wishlist"
              aria-pressed={isWishlisted(product.id)}
            >
              <Heart aria-hidden />
            </button>
          </div>

          <ul className="pdp-perks">
            <li><Truck aria-hidden /> Free delivery on orders above ₹999</li>
            <li><RotateCcw aria-hidden /> 15-day easy returns</li>
            <li><ShieldCheck aria-hidden /> 1-year warranty & secure checkout</li>
          </ul>
        </div>
      </div>

      <Reveal className="pdp-tabs">
        <div className="tab-list" role="tablist">
          {TABS.map((name) => (
            <button key={name} type="button" role="tab" aria-selected={tab === name} className={tab === name ? "active" : ""} onClick={() => setTab(name)}>
              {name}
            </button>
          ))}
        </div>
        <div className="tab-panel fade-up" key={tab} role="tabpanel">
          {tab === "Description" ? <p>{product.description}</p> : null}
          {tab === "Highlights" ? (
            <ul className="check-list">
              {product.highlights.map((h) => <li key={h}><Check aria-hidden /> {h}</li>)}
            </ul>
          ) : null}
          {tab === "Shipping & returns" ? (
            <p>
              Dispatched within 24 hours. Delivered in 2–7 business days depending on your pincode. Returns accepted within 15 days of delivery —
              see our <Link to="/policies/$slug" params={{ slug: "returns" }}>returns policy</Link>.
            </p>
          ) : null}
        </div>
      </Reveal>

      {related.length > 0 ? (
        <section className="section">
          <SectionHeader eyebrow="Keep exploring" title="You may also like" />
          <ProductRail products={related} />
        </section>
      ) : null}
    </div>
  );
}
