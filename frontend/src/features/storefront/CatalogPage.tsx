import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { PackageSearch, SlidersHorizontal, X } from "lucide-react";
import { SheetSelect } from "../../components/sheet";
import { EmptyState, PageHero, ProductGrid } from "./components";
import { CATEGORIES, categoryBySlug, PRODUCTS } from "./demo-catalog";

export interface CatalogSearch {
  category?: string;
  q?: string;
  sort?: string;
  sale?: boolean;
}

const SORTS = [
  { value: "featured", label: "Featured" },
  { value: "popular", label: "Most popular" },
  { value: "newest", label: "Newest" },
  { value: "price-asc", label: "Price: low to high" },
  { value: "price-desc", label: "Price: high to low" },
  { value: "rating", label: "Top rated" },
];

const PRICE_BANDS = [
  { id: "all", label: "Any price", min: 0, max: Infinity },
  { id: "u1k", label: "Under ₹1,000", min: 0, max: 1000 },
  { id: "1-3k", label: "₹1,000 – ₹3,000", min: 1000, max: 3000 },
  { id: "3-6k", label: "₹3,000 – ₹6,000", min: 3000, max: 6000 },
  { id: "6k", label: "Above ₹6,000", min: 6000, max: Infinity },
];

export function CatalogPage({ search }: { search: CatalogSearch }) {
  const navigate = useNavigate({ from: "/shop/" });
  const [band, setBand] = useState("all");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const sort = search.sort ?? "featured";
  const category = categoryBySlug(search.category);

  const update = (patch: Partial<CatalogSearch>) =>
    void navigate({ search: (previous) => ({ ...previous, ...patch }), resetScroll: false });

  const products = useMemo(() => {
    const priceBand = PRICE_BANDS.find((b) => b.id === band) ?? PRICE_BANDS[0]!;
    const q = search.q?.toLowerCase().trim();
    const list = PRODUCTS.filter((product) => {
      const price = Number(product.price);
      if (search.category && product.category !== search.category) return false;
      if (search.sale && !product.compareAt) return false;
      if (price < priceBand.min || price >= priceBand.max) return false;
      if (q && !`${product.name} ${product.description} ${product.category}`.toLowerCase().includes(q)) return false;
      return true;
    });
    switch (sort) {
      case "popular": return list.sort((a, b) => b.reviews - a.reviews);
      case "newest": return list.sort((a, b) => Number(b.badge === "New") - Number(a.badge === "New"));
      case "price-asc": return list.sort((a, b) => Number(a.price) - Number(b.price));
      case "price-desc": return list.sort((a, b) => Number(b.price) - Number(a.price));
      case "rating": return list.sort((a, b) => b.rating - a.rating);
      default: return list;
    }
  }, [search.category, search.q, search.sale, sort, band]);

  const hasFilters = Boolean(search.category || search.q || search.sale || band !== "all");

  return (
    <>
      <PageHero
        title={category ? category.name : search.q ? `Results for “${search.q}”` : "Shop all products"}
        text={category ? category.blurb : "Everyday essentials and standout finds, hand-picked for you."}
        tone={category?.tone ?? "indigo"}
      />
      <div className="shop-container catalog">
        <aside className={`filters ${filtersOpen ? "open" : ""}`}>
          <div className="filters-head">
            <strong>Filters</strong>
            <button type="button" className="icon-btn filters-close" onClick={() => setFiltersOpen(false)} aria-label="Close filters">
              <X aria-hidden />
            </button>
          </div>
          <div className="filter-group">
            <h4>Category</h4>
            <button type="button" className={`filter-pill ${!search.category ? "active" : ""}`} onClick={() => update({ category: undefined })}>
              All
            </button>
            {CATEGORIES.map((c) => (
              <button
                key={c.slug}
                type="button"
                className={`filter-pill ${search.category === c.slug ? "active" : ""}`}
                onClick={() => update({ category: c.slug })}
              >
                {c.name}
              </button>
            ))}
          </div>
          <div className="filter-group">
            <h4>Price</h4>
            {PRICE_BANDS.map((b) => (
              <button key={b.id} type="button" className={`filter-pill ${band === b.id ? "active" : ""}`} onClick={() => setBand(b.id)}>
                {b.label}
              </button>
            ))}
          </div>
          <div className="filter-group">
            <h4>Offers</h4>
            <label className="check-row">
              <input type="checkbox" checked={Boolean(search.sale)} onChange={(event) => update({ sale: event.target.checked || undefined })} />
              On sale only
            </label>
          </div>
        </aside>
        <div className={`drawer-backdrop filters-backdrop ${filtersOpen ? "open" : ""}`} onClick={() => setFiltersOpen(false)} />

        <div className="catalog-main">
          <div className="catalog-bar">
            <button type="button" className="btn-ghost filters-toggle" onClick={() => setFiltersOpen(true)}>
              <SlidersHorizontal aria-hidden /> Filters
            </button>
            <span className="result-count">{products.length} products</span>
            {hasFilters ? (
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setBand("all");
                  void navigate({ search: { sort: search.sort } });
                }}
              >
                Clear filters
              </button>
            ) : null}
            <div className="sort-select">
              <SheetSelect
                value={sort}
                options={SORTS}
                onChange={(value) => update({ sort: value === "featured" ? undefined : value })}
                title="Sort products"
                searchPlaceholder="Search sort options…"
              />
            </div>
          </div>
          {products.length > 0 ? (
            <ProductGrid key={`${search.category}-${search.q}-${sort}-${band}-${search.sale}`} products={products} />
          ) : (
            <EmptyState
              icon={<PackageSearch aria-hidden />}
              title="No products match"
              text="Try a different search or loosen the filters."
            />
          )}
        </div>
      </div>
    </>
  );
}
