import { createFileRoute } from "@tanstack/react-router";
import { ShopProvider } from "../features/storefront/shop-state";
import { StoreProvider } from "../features/storefront/store-context";
import { ShopLayout } from "../features/storefront/ShopLayout";
// Styles for the content pages (about, contact, FAQ, policies, …). Every rule
// is scoped under `.shop`, so it cannot leak into the ERP shell.
import "../features/storefront/shop.css";

/**
 * Pathless layout for the public storefront. No auth guard: every page under
 * it is reachable by anonymous visitors. It installs the two storefront
 * providers (resolved company + client-side cart/wishlist state).
 */
export const Route = createFileRoute("/_shop")({ component: PublicShopLayout });

function PublicShopLayout(): React.JSX.Element {
  return (
    <div className="shop">
      <StoreProvider>
        <ShopProvider>
          <ShopLayout />
        </ShopProvider>
      </StoreProvider>
    </div>
  );
}
