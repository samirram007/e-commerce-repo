import { createFileRoute } from "@tanstack/react-router";
import { OrderSuccessPage } from "../../features/storefront/InfoPages";

interface OrderSuccessSearch {
  order?: string;
  total?: string;
}

export const Route = createFileRoute("/_shop/order-success")({
  validateSearch: (search: Record<string, unknown>): OrderSuccessSearch => ({
    order: typeof search.order === "string" ? search.order : undefined,
    total: typeof search.total === "string" || typeof search.total === "number" ? String(search.total) : undefined,
  }),
  component: function OrderSuccessRoute() {
    const { order, total } = Route.useSearch();
    return <OrderSuccessPage order={order} total={total} />;
  },
});
