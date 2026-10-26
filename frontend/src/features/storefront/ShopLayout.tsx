<<<<<<< HEAD
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
=======
/** Public storefront chrome: announcement bar, sticky header, footer and toasts. */
import { useEffect, useState, type FormEvent } from "react";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { Heart, Mail, MapPin, Menu, Phone, Search, ShoppingBag, User, X } from "lucide-react";
import { useAuth } from "../../auth/auth-context";
import { CATEGORIES } from "./demo-catalog";
import { ShopProvider, useShop } from "./shop-state";
import "./shop.css";

const NAV = [
  { to: "/", label: "Home" },
  { to: "/shop", label: "Shop" },
  { to: "/categories", label: "Categories" },
  { to: "/deals", label: "Deals" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
] as const;

const ANNOUNCEMENTS = [
  "Free shipping on orders above ₹999",
  "Easy 15-day returns",
  "Festive sale — up to 30% off electronics",
  "Cash on delivery available",
  "New arrivals every Friday",
];

function AnnouncementBar() {
  // Duplicated list so the marquee loops seamlessly.
  const items = [...ANNOUNCEMENTS, ...ANNOUNCEMENTS];
  return (
    <div className="announce" aria-label="Store announcements">
      <div className="announce-track">
        {items.map((text, i) => (
          <span key={i} aria-hidden={i >= ANNOUNCEMENTS.length}>
            {text}
          </span>
        ))}
      </div>
    </div>
  );
}

function HeaderSearch({ onDone }: { onDone?: () => void }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    void navigate({ to: "/shop", search: { q: q.trim() || undefined } });
    onDone?.();
  }

  return (
    <form className="header-search" onSubmit={submit} role="search">
      <Search aria-hidden />
      <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Search products…" aria-label="Search products" />
    </form>
  );
}

function CountBadge({ count }: { count: number }) {
  if (count === 0) return null;
  // Keyed on the count so the bump animation replays on every change.
  return (
    <span className="count-badge" key={count}>
      {count}
    </span>
  );
}

function Header() {
  const { cartCount, wishlist } = useShop();
  const { isAuthenticated } = useAuth();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  return (
    <header className={`shop-header ${scrolled ? "scrolled" : ""}`}>
      <div className="shop-container header-row">
        <button type="button" className="icon-btn menu-btn" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Menu aria-hidden />
        </button>
        <Link to="/" className="logo">
          <span className="logo-mark">S</span>
          <span>Shopora</span>
        </Link>
        <nav className="main-nav" aria-label="Main">
          {NAV.map((item) => (
            <Link key={item.to} to={item.to} className={isActive(item.to) ? "active" : ""}>
              {item.label}
            </Link>
          ))}
        </nav>
        <HeaderSearch />
        <div className="header-actions">
          <Link to={isAuthenticated ? "/dashboard" : "/login"} className="icon-btn" aria-label={isAuthenticated ? "Dashboard" : "Sign in"}>
            <User aria-hidden />
          </Link>
          <Link to="/wishlist" className="icon-btn" aria-label={`Wishlist, ${wishlist.length} items`}>
            <Heart aria-hidden />
            <CountBadge count={wishlist.length} />
          </Link>
          <Link to="/cart" className="icon-btn" aria-label={`Bag, ${cartCount} items`}>
            <ShoppingBag aria-hidden />
            <CountBadge count={cartCount} />
          </Link>
        </div>
      </div>

      <div className={`drawer-backdrop ${menuOpen ? "open" : ""}`} onClick={() => setMenuOpen(false)} />
      <aside className={`drawer ${menuOpen ? "open" : ""}`} aria-hidden={!menuOpen} aria-label="Menu">
        <div className="drawer-head">
          <span className="logo">
            <span className="logo-mark">S</span>
            <span>Shopora</span>
          </span>
          <button type="button" className="icon-btn" onClick={() => setMenuOpen(false)} aria-label="Close menu">
            <X aria-hidden />
          </button>
        </div>
        <HeaderSearch onDone={() => setMenuOpen(false)} />
        <nav className="drawer-nav">
          {NAV.map((item) => (
            <Link key={item.to} to={item.to} className={isActive(item.to) ? "active" : ""}>
              {item.label}
            </Link>
          ))}
          <Link to="/wishlist">Wishlist</Link>
          <Link to="/cart">Bag</Link>
          <Link to="/faq">Help & FAQ</Link>
        </nav>
      </aside>
    </header>
  );
}

function Footer() {
  const { notify } = useShop();
  const [email, setEmail] = useState("");

  function subscribe(event: FormEvent) {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      notify("Please enter a valid email address");
      return;
    }
    setEmail("");
    notify("Thanks for subscribing! Check your inbox for 10% off.");
  }

  return (
    <footer className="shop-footer">
      <div className="shop-container">
        <div className="newsletter">
          <div>
            <h3>Get 10% off your first order</h3>
            <p>Join the list for early access to drops, restocks and members-only deals.</p>
          </div>
          <form onSubmit={subscribe} className="newsletter-form">
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              aria-label="Email address"
            />
            <button type="submit" className="btn-primary">Subscribe</button>
          </form>
        </div>

        <div className="footer-grid">
          <div>
            <Link to="/" className="logo">
              <span className="logo-mark">S</span>
              <span>Shopora</span>
            </Link>
            <p className="footer-about">Thoughtfully chosen everyday essentials, delivered across India.</p>
            <ul className="footer-contact">
              <li><MapPin aria-hidden /> 42 Market Street, Bengaluru 560001</li>
              <li><Phone aria-hidden /> +91 80 4000 1234</li>
              <li><Mail aria-hidden /> hello@shopora.example</li>
            </ul>
          </div>
          <div>
            <h4>Shop</h4>
            {CATEGORIES.map((category) => (
              <Link key={category.slug} to="/shop" search={{ category: category.slug }}>
                {category.name}
              </Link>
            ))}
          </div>
          <div>
            <h4>Help</h4>
            <Link to="/faq">FAQ</Link>
            <Link to="/policies/$slug" params={{ slug: "shipping" }}>Shipping</Link>
            <Link to="/policies/$slug" params={{ slug: "returns" }}>Returns & refunds</Link>
            <Link to="/contact">Contact us</Link>
          </div>
          <div>
            <h4>Company</h4>
            <Link to="/about">About us</Link>
            <Link to="/policies/$slug" params={{ slug: "privacy" }}>Privacy policy</Link>
            <Link to="/policies/$slug" params={{ slug: "terms" }}>Terms of service</Link>
            <Link to="/login">Staff sign in</Link>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} Shopora. All rights reserved.</span>
          <span className="pay-chips">
            <span>UPI</span><span>VISA</span><span>Mastercard</span><span>RuPay</span><span>COD</span>
          </span>
        </div>
      </div>
    </footer>
  );
}

function Toasts() {
  const { toasts } = useShop();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className="toast">
          {toast.text}
        </div>
      ))}
    </div>
  );
}

/** Scrolls back to the top whenever the route path changes. */
function ScrollToTop() {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);
  return null;
}

export function ShopLayout() {
  return (
    <ShopProvider>
      <div className="shop">
        <ScrollToTop />
        <AnnouncementBar />
        <Header />
        <main className="shop-main">
          <Outlet />
        </main>
        <Footer />
        <Toasts />
      </div>
    </ShopProvider>
  );
}
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
