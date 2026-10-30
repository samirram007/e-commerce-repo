import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatMoney } from "../../lib/format";
import { addCartItem, toggleInterest } from "./api";
import { interestsQueryOptions, shopKeys } from "./queries";
import { useStoreCurrency } from "./store-context";
import { ProductImage } from "./ProductImage";
import type { ShopProduct } from "./types";

interface Props {
  product: ShopProduct;
  showInterest?: boolean;
}

export function ProductCard({ product, showInterest = true }: Props) {
  const currency = useStoreCurrency();
  const qc = useQueryClient();
  const interests = useQuery(interestsQueryOptions());
  const isFavorite = interests.data?.favorite?.some((p) => p.id === product.id) ?? false;
  const isWatched = interests.data?.watchlist?.some((p) => p.id === product.id) ?? false;

  const [added, setAdded] = useState(false);

  const toggle = useMutation({
    mutationFn: (kind: "favorite" | "watchlist") => toggleInterest(kind, product.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: shopKeys.interests }),
  });

  const addToCart = useMutation({
    mutationFn: (qty: string) => addCartItem(product.id, qty),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: shopKeys.cart });
      setAdded(true);
      setTimeout(() => setAdded(false), 1600);
    },
  });

  return (
    <article className="shop-product-card">
      <Link
        to="/shop/$productId"
        params={{ productId: product.id }}
        className="shop-product-img"
        aria-label={product.name}
      >
        <ProductImage name={product.name} sku={product.sku} imageUrl={product.image_url} />
        <span className="shop-product-sku">{product.sku}</span>
      </Link>

      {showInterest ? (
        <div className="shop-product-actions">
          <button
            type="button"
            className={`shop-icon-btn ${isFavorite ? "active" : ""}`}
            title={isFavorite ? "Remove from favorites" : "Add to favorites"}
            aria-pressed={isFavorite}
            onClick={() => toggle.mutate("favorite")}
            disabled={toggle.isPending}
          >
            {isFavorite ? "♥" : "♡"}
          </button>
          <button
            type="button"
            className={`shop-icon-btn ${isWatched ? "active" : ""}`}
            title={isWatched ? "Remove from watchlist" : "Add to watchlist"}
            aria-pressed={isWatched}
            onClick={() => toggle.mutate("watchlist")}
            disabled={toggle.isPending}
          >
            {isWatched ? "★" : "☆"}
          </button>
        </div>
      ) : null}

      <div className="shop-product-body">
        <Link
          to="/shop/$productId"
          params={{ productId: product.id }}
          className="shop-product-name"
        >
          {product.name}
        </Link>
        {product.description ? <p className="shop-product-desc muted">{product.description}</p> : null}
        <div className="shop-product-foot">
          <span className="shop-product-price">{formatMoney(product.price, currency)}</span>
          <button
            type="button"
            className="shop-add-to-cart"
            onClick={() => addToCart.mutate("1")}
            disabled={addToCart.isPending}
          >
            {addToCart.isPending ? "Adding…" : added ? "Added ✓" : "Add to cart"}
          </button>
        </div>
        {addToCart.isError ? (
          <span className="shop-card-error">{(addToCart.error as Error).message}</span>
        ) : null}
      </div>
    </article>
  );
}
