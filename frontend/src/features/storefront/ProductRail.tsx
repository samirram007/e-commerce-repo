import { Link } from "@tanstack/react-router";
import { EmptyState, Spinner } from "../../components/ui";
import { ProductCard } from "./ProductCard";
import type { ShopProduct } from "./types";

interface Props {
  title: string;
  subtitle?: string;
  products: ShopProduct[] | undefined;
  loading?: boolean;
  error?: unknown;
  /** Search filters for the "View all" link into the catalog. */
  viewAll?: { category?: string; sort?: "newest" | "price_asc" | "price_desc" | "name" };
  emptyMessage?: string;
}

/** A horizontally scrolling product panel — one per catalog story. */
export function ProductRail({
  title,
  subtitle,
  products,
  loading = false,
  error,
  viewAll,
  emptyMessage = "Nothing here yet.",
}: Props) {
  const items = products ?? [];

  return (
    <section className="shop-section">
      <div className="shop-section-head">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className="shop-section-sub muted">{subtitle}</p> : null}
        </div>
        {viewAll ? (
          <Link to="/shop" search={viewAll} className="shop-text-link">
            View all →
          </Link>
        ) : null}
      </div>

      {loading ? (
        <Spinner />
      ) : error ? (
        <EmptyState title={`Could not load ${title.toLowerCase()}`} message={(error as Error).message} />
      ) : items.length === 0 ? (
        <EmptyState title={emptyMessage} />
      ) : (
        <div className="shop-rail">
          {items.map((product) => (
            <div key={product.id} className="shop-rail-item">
              <ProductCard product={product} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
