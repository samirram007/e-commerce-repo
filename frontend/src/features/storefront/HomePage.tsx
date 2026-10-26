import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  categoriesQueryOptions,
  productsQueryOptions,
  trendingQueryOptions,
} from "./queries";
import { ProductRail } from "./ProductRail";
import { EmptyState, Spinner } from "../../components/ui";
import { useStore } from "./store-context";
import type { ShopCategory } from "./types";

function CategoryRail({ category }: { category: ShopCategory }) {
  const products = useQuery(
    productsQueryOptions({ category: category.id, sort: "newest", limit: 8 }),
  );

  return (
    <ProductRail
      title={`Top picks in ${category.name}`}
      subtitle={`${category.product_count} product${category.product_count === 1 ? "" : "s"}`}
      products={products.data?.items}
      loading={products.isLoading}
      error={products.isError ? products.error : undefined}
      viewAll={{ category: category.id }}
      emptyMessage="Nothing in this category yet."
    />
  );
}

export function HomePage() {
  const categories = useQuery(categoriesQueryOptions());
  const trending = useQuery(trendingQueryOptions(8));
  const newest = useQuery(productsQueryOptions({ sort: "newest", limit: 8 }));
  const budget = useQuery(productsQueryOptions({ sort: "price_asc", limit: 8 }));
  const { store } = useStore();

  // Largest departments get their own rail (parents already include children).
  const topCategories = useMemo(
    () =>
      [...(categories.data ?? [])]
        .filter((c) => c.product_count > 0)
        .sort((a, b) => b.product_count - a.product_count || a.name.localeCompare(b.name))
        .slice(0, 3),
    [categories.data],
  );

  return (
    <div className="shop-page">
      <section className="shop-hero">
        <span className="shop-hero-eyebrow">Welcome</span>
        <h1 className="shop-hero-title">{store?.name ?? "The store"}</h1>
        <p className="shop-hero-sub">
          Browse the catalog, save what you love, and check out in a couple of clicks.
        </p>
        <div className="shop-hero-actions">
          <Link to="/shop/products" className="btn shop-hero-cta">
            Shop all products
          </Link>
          <a href="#categories" className="btn secondary shop-hero-cta">
            Browse categories
          </a>
        </div>
        <div className="shop-hero-badges">
          {store?.allow_guest_checkout ? <span className="badge ok">Guest checkout</span> : null}
          <span className="badge">Prices in {store?.currency ?? "INR"}</span>
          <span className="badge">Pincode delivery check</span>
        </div>
      </section>

      <section className="shop-section" id="categories">
        <div className="shop-section-head">
          <h2>Categories</h2>
          <Link to="/shop/products" className="shop-text-link">
            All products →
          </Link>
        </div>
        {categories.isLoading ? (
          <Spinner />
        ) : categories.isError ? (
          <EmptyState title="Could not load categories" />
        ) : (categories.data?.length ?? 0) === 0 ? (
          <EmptyState title="No categories yet" />
        ) : (
          <div className="shop-category-grid">
            {categories.data!.map((c) => (
              <Link
                key={c.id}
                to="/shop/products"
                search={{ category: c.id }}
                className="shop-category-card"
              >
                <span className="shop-category-name">{c.name}</span>
                <span className="muted">
                  {c.product_count} item{c.product_count === 1 ? "" : "s"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <ProductRail
        title="Trending now"
        subtitle="What other shoppers are viewing"
        products={trending.data}
        loading={trending.isLoading}
        error={trending.isError ? trending.error : undefined}
        emptyMessage="No trending products yet."
      />

      <ProductRail
        title="New arrivals"
        subtitle="Freshly added to the catalog"
        products={newest.data?.items}
        loading={newest.isLoading}
        error={newest.isError ? newest.error : undefined}
        viewAll={{ sort: "newest" }}
      />

      <ProductRail
        title="Budget picks"
        subtitle="Great value, lowest price first"
        products={budget.data?.items}
        loading={budget.isLoading}
        error={budget.isError ? budget.error : undefined}
        viewAll={{ sort: "price_asc" }}
      />

      {topCategories.map((category) => (
        <CategoryRail key={category.id} category={category} />
      ))}
    </div>
  );
}
