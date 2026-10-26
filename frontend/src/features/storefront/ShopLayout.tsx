import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { EmptyState, Spinner } from "../../components/ui";
import { useStore } from "./store-context";
import { useAuth } from "../../auth/auth-context";
import { cartQueryOptions } from "./queries";
import { shopSignInHref } from "./routing";

export function ShopLayout() {
  const { store, loading, error } = useStore();
  const cart = useQuery({ ...cartQueryOptions(), enabled: !loading && !!store });
  const cartCount =
    cart.data?.items?.reduce((sum, item) => sum + Number(item.qty || 0), 0) ?? 0;
  const { isAuthenticated, logout } = useAuth();

  // Current shop URL (path + search), used to return here after signing in.
  const locationHref = useRouterState({ select: (state) => state.location.href });
  const signInHref = shopSignInHref(locationHref);

  if (loading) {
    return (
      <div className="shop-shell">
        <main className="shop-main">
          <Spinner />
        </main>
      </div>
    );
  }
  if (error || !store) {
    return (
      <div className="shop-shell">
        <main className="shop-main">
          <EmptyState title="Store unavailable" message="Could not resolve this storefront." />
        </main>
      </div>
    );
  }

  return (
    <div className="shop-shell">
      <header className="shop-header">
        <div className="shop-header-inner">
          <Link to="/shop" className="shop-brand">
            {store.name}
          </Link>
          <nav className="shop-nav">
            <div className="shop-nav-links-left">
              <Link
                to="/shop"
                className="shop-nav-link"
                activeProps={{ className: "active" }}
                activeOptions={{ exact: true }}
              >
                Home
              </Link>
              <Link to="/shop/products" className="shop-nav-link" activeProps={{ className: "active" }}>
                Products
              </Link>
            </div>
            <div className="shop-nav-links-right">
              <Link to="/shop/interests" className="shop-nav-link" activeProps={{ className: "active" }}>
                Wishlist
              </Link>
              <Link to="/shop/orders" className="shop-nav-link" activeProps={{ className: "active" }}>
                Orders
              </Link>
            </div>
            <Link to="/shop/cart" className="shop-cart-link">
              Cart
              {cartCount > 0 ? <span className="shop-cart-badge">{cartCount}</span> : null}
            </Link>
            {isAuthenticated ? (
              <span className="shop-nav-link shop-account">
                {store.currency}
                <button
                  type="button"
                  className="shop-signout"
                  onClick={(event) => {
                    event.stopPropagation();
                    logout();
                  }}
                >
                  Sign out
                </button>
              </span>
            ) : (
              <span className="shop-nav-link shop-signin">
                <a href={signInHref}>Sign in</a>
              </span>
            )}
          </nav>
        </div>
      </header>

      <main className="shop-main">
        <Outlet />
      </main>

      <footer className="shop-footer">
        <div className="shop-footer-inner">
          <span className="muted">
            {store.name} · {store.currency}
          </span>
          <span className="muted">Powered by ERP</span>
        </div>
      </footer>
    </div>
  );
}
