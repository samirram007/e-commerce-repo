import { createFileRoute } from "@tanstack/react-router";
import { OrdersPage } from "../../features/storefront/OrdersPage";

export const Route = createFileRoute("/shop/orders")({
  component: OrdersPage,
});