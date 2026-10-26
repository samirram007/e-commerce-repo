import { createFileRoute } from "@tanstack/react-router";
import { CatalogPage, type CatalogSearch } from "../../features/storefront/CatalogPage";

const str = (value: unknown): string | undefined => (typeof value === "string" && value !== "" ? value : undefined);

export const Route = createFileRoute("/_shop/shop/")({
  validateSearch: (search: Record<string, unknown>): CatalogSearch => ({
    category: str(search.category),
    q: str(search.q),
    sort: str(search.sort),
    sale: search.sale === true || search.sale === "true" ? true : undefined,
  }),
  component: function ShopRoute() {
    return <CatalogPage search={Route.useSearch()} />;
  },
});
