import { createFileRoute, Outlet } from "@tanstack/react-router";

/**
 * Pass-through layout for the `/shop/*` subtree so the catalog (`/shop/`), a
 * single product (`/shop/$productId`) and the signed-in shopper screens
 * (`/shop/orders`, `/shop/wishlist`) sit side by side.
 */
export const Route = createFileRoute("/_shop/shop")({ component: Outlet });
