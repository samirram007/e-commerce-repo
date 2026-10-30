import { createFileRoute, redirect } from "@tanstack/react-router";
import { ensureSession } from "../../auth/auth-context";
import { InterestsPage } from "../../features/storefront/InterestsPage";

/** Saved products for the signed-in shopper — a protected page, never public. */
export const Route = createFileRoute("/_shop/shop/wishlist")({
  beforeLoad: async () => {
    if (!(await ensureSession())) {
      throw redirect({ to: "/login", search: { redirect: "/shop/wishlist" } });
    }
  },
  component: InterestsPage,
});
