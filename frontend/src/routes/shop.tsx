import { createFileRoute } from "@tanstack/react-router";
import { StoreProvider } from "../features/storefront/store-context";
import { ShopLayout } from "../features/storefront/ShopLayout";

export const Route = createFileRoute("/shop")({
  component: ShopRoute,
});

function ShopRoute() {
  return (
    <StoreProvider>
      <ShopLayout />
    </StoreProvider>
  );
}