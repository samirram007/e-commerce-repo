import { createFileRoute, Outlet } from "@tanstack/react-router";

/**
 * Layout for `/shop/products/*`. It must render `<Outlet/>`: without it the
 * child `$productId` route (single product page) never mounts and the URL
 * simply shows the product list.
 */
export const Route = createFileRoute("/shop/products")({
  component: ShopProductsLayout,
});

function ShopProductsLayout() {
  return <Outlet />;
}
