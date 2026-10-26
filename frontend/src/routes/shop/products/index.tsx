import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { ProductsPage } from "../../../features/storefront/ProductsPage";

/** Deep-linkable catalog filters: /shop/products?category=…&q=…&sort=… */
const productsSearchSchema = z.object({
  category: z.string().optional(),
  q: z.string().optional(),
  sort: z.enum(["newest", "price_asc", "price_desc", "name"]).optional(),
});

export type ProductsSearch = z.infer<typeof productsSearchSchema>;

export const Route = createFileRoute("/shop/products/")({
  validateSearch: (search: Record<string, unknown>): ProductsSearch => {
    const parsed = productsSearchSchema.safeParse(search);
    return parsed.success ? parsed.data : {};
  },
  component: ProductsIndexRoute,
});

function ProductsIndexRoute() {
  const { category, q, sort } = Route.useSearch();
  return <ProductsPage initialCategory={category} initialQuery={q} initialSort={sort} />;
}
