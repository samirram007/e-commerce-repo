import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { categoriesQueryOptions, productsQueryOptions } from "./queries";
import { ProductCard } from "./ProductCard";
import { SheetSelect } from "../../components/sheet";
import { Button, EmptyState, Field, Input, Spinner } from "../../components/ui";

/** Matches the backend `SORTS` keys; the catalog defaults to newest first. */
const DEFAULT_SORT = "newest";
const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "name", label: "Name A–Z" },
];

const PAGE_SIZES = [12, 24, 48];

interface Props {
  /** Deep-linked filters from /shop/products?category=…&q=…&sort=… (home rails). */
  initialCategory?: string;
  initialQuery?: string;
  initialSort?: string;
}

export function ProductsPage({ initialCategory, initialQuery, initialSort }: Props = {}) {
  const [qInput, setQInput] = useState(initialQuery ?? "");
  const [q, setQ] = useState(initialQuery ?? "");
  const [category, setCategory] = useState(initialCategory ?? "");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sort, setSort] = useState(initialSort ?? DEFAULT_SORT);
  const [limit, setLimit] = useState(12);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [qInput]);

  const categories = useQuery(categoriesQueryOptions());
  const categoryOptions = useMemo(
    () => [
      { value: "", label: "All categories" },
      ...(categories.data?.map((c) => ({ value: c.id, label: c.name })) ?? []),
    ],
    [categories.data],
  );

  const filters = useMemo(
    () => ({
      q: q.trim() || undefined,
      category: category || undefined,
      minPrice: minPrice || undefined,
      maxPrice: maxPrice || undefined,
      sort,
      limit,
      offset,
    }),
    [q, category, minPrice, maxPrice, sort, limit, offset],
  );

  const products = useQuery(productsQueryOptions(filters));

  const reset = () => {
    setQInput("");
    setQ("");
    setCategory("");
    setMinPrice("");
    setMaxPrice("");
    setSort(DEFAULT_SORT);
    setLimit(12);
    setOffset(0);
  };

  const total = products.data?.total ?? 0;
  const items = products.data?.items ?? [];
  const hasFilters = !!(qInput || category || minPrice || maxPrice || sort !== DEFAULT_SORT);

  return (
    <div className="shop-page">
      <h1 className="page-title">Products</h1>

      <div className="shop-filters">
        <Field label="Search">
          <Input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Search products…"
          />
        </Field>
        <Field label="Category">
          <SheetSelect
            value={category}
            options={categoryOptions}
            onChange={(v) => {
              setCategory(v);
              setOffset(0);
            }}
            placeholder="All categories"
            loading={categories.isLoading}
          />
        </Field>
        <Field label="Min price">
          <Input
            type="number"
            value={minPrice}
            onChange={(e) => {
              setMinPrice(e.target.value);
              setOffset(0);
            }}
            placeholder="0"
          />
        </Field>
        <Field label="Max price">
          <Input
            type="number"
            value={maxPrice}
            onChange={(e) => {
              setMaxPrice(e.target.value);
              setOffset(0);
            }}
            placeholder="∞"
          />
        </Field>
        <Field label="Sort">
          <SheetSelect
            value={sort}
            options={SORT_OPTIONS}
            onChange={(v) => {
              setSort(v || DEFAULT_SORT);
              setOffset(0);
            }}
            placeholder="Newest"
          />
        </Field>
        <Field label="Page size">
          <SheetSelect
            value={String(limit)}
            options={PAGE_SIZES.map((n) => ({ value: String(n), label: String(n) }))}
            onChange={(v) => {
              setLimit(Number(v) || 12);
              setOffset(0);
            }}
            placeholder="12"
          />
        </Field>
      </div>

      {products.isLoading ? (
        <Spinner />
      ) : products.isError ? (
        <EmptyState title="Could not load products" message={(products.error as Error).message} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No products match"
          message={hasFilters ? "Try adjusting or resetting your filters." : "Check back later."}
          action={hasFilters ? <Button onClick={reset}>Reset filters</Button> : undefined}
        />
      ) : (
        <>
          <div className="shop-results-head">
            <h2>{hasFilters ? "Filtered products" : "All products"}</h2>
            <div className="shop-results-meta">
              <span className="muted">
                {total} product{total === 1 ? "" : "s"}
              </span>
              {hasFilters ? (
                <Button variant="secondary" onClick={reset}>
                  Reset filters
                </Button>
              ) : null}
            </div>
          </div>
          <div className="shop-product-grid">
            {items.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
          <div className="shop-pagination">
            <Button
              variant="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </Button>
            <span className="muted">
              {Math.min(offset + 1, total)}–{Math.min(offset + limit, total)} of {total}
            </span>
            <Button
              variant="secondary"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}