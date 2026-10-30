import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addCartItem, toggleInterest } from "./api";
import {
  productQueryOptions,
  interestsQueryOptions,
  isValidPincode,
  pincodeQueryOptions,
  shopKeys,
} from "./queries";
import { ProductCard } from "./ProductCard";
import { ReviewsSection } from "./ReviewsSection";
import { ProductImage } from "./ProductImage";
import { Button, EmptyState, Field, Input, Spinner } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import { useStoreCurrency } from "./store-context";

export function ProductDetailPage({ productId: productIdProp }: { productId?: string } = {}) {
  // Robust fallback: if the route didn't pass the param, parse it from the URL.
  let productId = productIdProp;
  if (!productId && typeof window !== "undefined") {
    const parts = window.location.pathname.split("/").filter(Boolean);
    const idx = parts.indexOf("products");
    if (idx >= 0 && parts[idx + 1]) productId = parts[idx + 1];
  }
  const qc = useQueryClient();
  const currency = useStoreCurrency();
  const product = useQuery({ ...productQueryOptions(productId ?? "", true), enabled: !!productId });
  const interests = useQuery(interestsQueryOptions());

  const isFavorite = interests.data?.favorite?.some((p) => p.id === productId) ?? false;
  const isWatched = interests.data?.watchlist?.some((p) => p.id === productId) ?? false;

  const [qty, setQty] = useState("1");
  const [pincode, setPincode] = useState("");
  const [added, setAdded] = useState(false);

  const add = useMutation({
    mutationFn: () => {
      if (!productId) throw new Error("Missing product");
      return addCartItem(productId, qty || "1");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: shopKeys.cart });
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
    },
    onError: (err) => {
      // eslint-disable-next-line no-console
      console.error("add to cart failed", err);
    },
  });

  const toggle = useMutation({
    mutationFn: (kind: "favorite" | "watchlist") => {
      if (!productId) throw new Error("Missing product");
      return toggleInterest(kind, productId);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: shopKeys.interests }),
  });

  const pincodeQuery = useQuery(pincodeQueryOptions(pincode));

  if (!productId) {
    return <EmptyState title="Product not found" />;
  }
  if (product.isLoading) return <Spinner />;
  if (product.isError || !product.data) return <EmptyState title="Product not found" />;

  const p = product.data;

  return (
    <div className="shop-page">
      <nav className="shop-breadcrumb muted">
        <Link to="/shop">Products</Link>
        <span> / </span>
        <span>{p.name}</span>
      </nav>

      <div className="shop-pdp">
        <div className="shop-pdp-media">
          <ProductImage name={p.name} sku={p.sku} imageUrl={p.image_url} large />
          <span className="shop-product-sku">{p.sku}</span>
        </div>
        <div className="shop-pdp-info">
          {p.category_name ? <span className="shop-pdp-eyebrow">{p.category_name}</span> : null}
          <h1 className="page-title">{p.name}</h1>
          {p.description ? <p className="shop-pdp-desc">{p.description}</p> : null}
          <div className="shop-pdp-price">
            {formatMoney(p.price, currency)}
            <span className="shop-pdp-price-note muted">incl. taxes</span>
          </div>
          <div className="shop-pdp-badges">
            <span className={`badge ${p.stock_type === "stock" ? "ok" : "warn"}`}>
              {p.stock_type === "stock" ? "In stock" : p.stock_type === "service" ? "Service" : "Made to order"}
            </span>
            {p.view_count > 0 ? <span className="badge">{p.view_count} views</span> : null}
          </div>

          <div className="shop-pdp-buy">
            <label className="shop-qty-field">
              <span className="muted">Qty</span>
              <Input type="number" min="1" value={qty} onChange={(e) => setQty(e.target.value)} />
            </label>
            <Button onClick={() => add.mutate()} disabled={add.isPending || !productId}>
              {add.isPending ? "Adding…" : added ? "Added ✓" : "Add to cart"}
            </Button>
            <Link to="/cart" className="btn secondary shop-pdp-cart-link">
              View cart
            </Link>
          </div>
          {add.isError ? (
            <p className="error-text">{(add.error as Error).message || "Could not add to cart"}</p>
          ) : null}

          <div className="shop-pdp-interests">
            <button
              type="button"
              className={`shop-icon-btn ${isFavorite ? "active" : ""}`}
              onClick={() => toggle.mutate("favorite")}
              disabled={toggle.isPending}
            >
              {isFavorite ? "♥ Favorited" : "♡ Favorite"}
            </button>
            <button
              type="button"
              className={`shop-icon-btn ${isWatched ? "active" : ""}`}
              onClick={() => toggle.mutate("watchlist")}
              disabled={toggle.isPending}
            >
              {isWatched ? "★ Watching" : "☆ Watchlist"}
            </button>
          </div>

          <div className="shop-pincode">
            <Field label="Check delivery PIN code">
              <Input
                value={pincode}
                onChange={(e) => setPincode(e.target.value)}
                placeholder="e.g. 560001"
                inputMode="numeric"
                maxLength={6}
              />
            </Field>
            {pincode.trim().length > 0 && !isValidPincode(pincode) ? (
              <p className="shop-hint">Enter a 6-digit Indian PIN code (it cannot start with 0).</p>
            ) : null}
            {isValidPincode(pincode) ? (
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
          </div>
        </div>
      </div>

      <section className="shop-section shop-section-reviews">
        <ReviewsSection productId={p.id} />
      </section>

      {p.related && p.related.length > 0 ? (
        <section className="shop-section">
          <div className="shop-section-head">
            <h2>Related products</h2>
          </div>
          <div className="shop-product-grid">
            {p.related.map((r) => (
              <ProductCard key={r.id} product={r} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}