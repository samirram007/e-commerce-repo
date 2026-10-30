import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  CircleHelp,
  Heart,
  House,
  Info,
  LayoutDashboard,
  LayoutGrid,
  LogIn,
  Mail,
  Package,
  Percent,
  Search,
  ShoppingBag,
  ShoppingCart,
  UserPlus,
  X,
} from "lucide-react";
import { EmptyState, Spinner } from "../../components/ui";
import { useStore } from "./store-context";
import { useAuth } from "../../auth/auth-context";
import { cartQueryOptions } from "./queries";
import { shopSignInHref } from "./routing";

/**
 * Every topbar menu entry, in order — all of them share the same icon+label
 * style, so browsing, account and content pages read as one menu.
 */
const MENU = [
  { to: "/", label: "Home", icon: House },
  { to: "/shop", label: "Products", icon: ShoppingBag },
  { to: "/shop/wishlist", label: "Wishlist", icon: Heart },
  { to: "/shop/orders", label: "Orders", icon: Package },
  { to: "/categories", label: "Categories", icon: LayoutGrid },
  { to: "/deals", label: "Deals", icon: Percent },
  { to: "/about", label: "About", icon: Info },
  { to: "/contact", label: "Contact", icon: Mail },
  { to: "/faq", label: "Help", icon: CircleHelp },
] as const;

export function ShopLayout() {
  const { store, loading, error } = useStore();
  const cart = useQuery({ ...cartQueryOptions(), enabled: !loading && !!store });
  const cartCount =
    cart.data?.items?.reduce((sum, item) => sum + Number(item.qty || 0), 0) ?? 0;
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  // Current shop URL (path + search), used to return here after signing in.
  const locationHref = useRouterState({ select: (state) => state.location.href });
  const signInHref = shopSignInHref(locationHref);

  // `⌘K` / `Ctrl+K` jumps to the search box from anywhere in the shop.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
      if (event.key === "Escape" && document.activeElement === searchRef.current) {
        searchRef.current?.blur();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const q = search.trim();
    void navigate({ to: "/shop", search: q ? { q } : {} });
  }

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
          <Link to="/" className="shop-brand">
            {store.name}
          </Link>

          <nav className="shop-nav">
            {MENU.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="shop-nav-link"
                activeProps={{ className: "active" }}
              >
                <item.icon size={24} aria-hidden />
                <span>{item.label}</span>
              </Link>
            ))}
            <Link to="/cart" className="shop-nav-link">
              <ShoppingCart size={24} aria-hidden />
              <span>Cart</span>
              {cartCount > 0 ? <span className="shop-cart-badge">{cartCount}</span> : null}
            </Link>
          </nav>

          <form className="shop-search" role="search" onSubmit={submitSearch}>
            <Search size={18} aria-hidden />
            <input
              ref={searchRef}
              type="search"
              value={search}
              aria-label="Search products"
              placeholder="Search products…"
              onChange={(event) => setSearch(event.target.value)}
            />
            {search ? (
              <button type="button" aria-label="Clear search" onClick={() => setSearch("")}>
                <X size={16} aria-hidden />
              </button>
            ) : (
              <kbd className="shop-search-key">Ctrl K</kbd>
            )}
          </form>

          <div className="shop-auth">
            {isAuthenticated ? (
              <>
                <Link to="/dashboard" className="shop-auth-link">
                  <LayoutDashboard size={24} aria-hidden />
                  <span>Dashboard</span>
                </Link>
                <span className="shop-auth-divider" aria-hidden />
                <span className="shop-auth-link shop-account">
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
              </>
            ) : (
              <>
                <a href={signInHref} className="shop-auth-link">
                  <LogIn size={24} aria-hidden />
                  <span>Sign in</span>
                </a>
                <span className="shop-auth-divider" aria-hidden />
                <a href="/register" className="shop-auth-link">
                  <UserPlus size={24} aria-hidden />
                  <span>Create account</span>
                </a>
              </>
            )}
          </div>
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
