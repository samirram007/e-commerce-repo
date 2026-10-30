import { createFileRoute, redirect } from "@tanstack/react-router";
import { ensureSession } from "../../auth/auth-context";
import { OrdersPage } from "../../features/storefront/OrdersPage";

/** The shopper's own order history — a protected page, never public. */
export const Route = createFileRoute("/_shop/shop/orders")({
  beforeLoad: async () => {
    if (!(await ensureSession())) {
      throw redirect({ to: "/login", search: { redirect: "/shop/orders" } });
    }
  },
  component: OrdersPage,
});
