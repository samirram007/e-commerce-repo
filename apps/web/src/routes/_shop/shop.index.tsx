import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { ProductsPage } from "../../features/storefront/ProductsPage";

/** Deep-linkable catalog filters: /shop?category=…&q=…&sort=… */
const shopSearchSchema = z.object({
  category: z.string().optional(),
  q: z.string().optional(),
  sort: z.enum(["newest", "price_asc", "price_desc", "name"]).optional(),
});

export type ShopSearch = z.infer<typeof shopSearchSchema>;

export const Route = createFileRoute("/_shop/shop/")({
  validateSearch: (search: Record<string, unknown>): ShopSearch => {
    const parsed = shopSearchSchema.safeParse(search);
    return parsed.success ? parsed.data : {};
  },
  component: function ShopIndexRoute() {
    const { category, q, sort } = Route.useSearch();
    // Keyed so a new search (topbar or deep link) re-runs the catalog query,
    // since the page seeds its state from these props on mount.
    return (
      <ProductsPage
        key={`${category ?? ""}|${q ?? ""}|${sort ?? ""}`}
        initialCategory={category}
        initialQuery={q}
        initialSort={sort}
      />
    );
  },
});
