/**
 * Client-side cart, wishlist and toast state for the public storefront.
 *
 * Persisted in localStorage so a reload keeps the shopper's bag. Lines are
 * keyed by product id and resolved against the demo catalog when rendered.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { FLAT_SHIPPING, FREE_SHIPPING_THRESHOLD, productById, type DemoProduct } from "./demo-catalog";

const CART_KEY = "shop.demoCart";
const WISHLIST_KEY = "shop.demoWishlist";

export interface CartLine {
  productId: string;
  qty: number;
}

export interface ResolvedLine extends CartLine {
  product: DemoProduct;
  lineTotal: number;
}

interface Toast {
  id: number;
  text: string;
}

interface ShopState {
  lines: ResolvedLine[];
  cartCount: number;
  subtotal: number;
  shipping: number;
  total: number;
  wishlist: string[];
  toasts: Toast[];
  addToCart: (productId: string, qty?: number) => void;
  setQty: (productId: string, qty: number) => void;
  removeFromCart: (productId: string) => void;
  clearCart: () => void;
  toggleWishlist: (productId: string) => void;
  isWishlisted: (productId: string) => boolean;
  notify: (text: string) => void;
}

const ShopContext = createContext<ShopState | null>(null);

function load<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage disabled: state just won't survive a reload
  }
}

export function ShopProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<CartLine[]>(() => load(CART_KEY, []));
  const [wishlist, setWishlist] = useState<string[]>(() => load(WISHLIST_KEY, []));
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastSeq = useRef(0);

  useEffect(() => {
    save(CART_KEY, cart);
  }, [cart]);
  useEffect(() => {
    save(WISHLIST_KEY, wishlist);
  }, [wishlist]);

  const notify = useCallback((text: string) => {
    const id = ++toastSeq.current;
    setToasts((current) => [...current, { id, text }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 2600);
  }, []);

  const addToCart = useCallback(
    (productId: string, qty = 1) => {
      setCart((current) => {
        const existing = current.find((line) => line.productId === productId);
        if (existing) {
          return current.map((line) => (line.productId === productId ? { ...line, qty: line.qty + qty } : line));
        }
        return [...current, { productId, qty }];
      });
      const product = productById(productId);
      if (product) notify(`${product.name} added to your bag`);
    },
    [notify],
  );

  const setQty = useCallback((productId: string, qty: number) => {
    setCart((current) =>
      qty <= 0
        ? current.filter((line) => line.productId !== productId)
        : current.map((line) => (line.productId === productId ? { ...line, qty } : line)),
    );
  }, []);

  const removeFromCart = useCallback((productId: string) => {
    setCart((current) => current.filter((line) => line.productId !== productId));
  }, []);

  const clearCart = useCallback(() => setCart([]), []);

  const toggleWishlist = useCallback(
    (productId: string) => {
      // Decide outside the updater: StrictMode runs updaters twice, which would double the toast.
      const active = wishlist.includes(productId);
      setWishlist((current) =>
        active ? current.filter((id) => id !== productId) : current.includes(productId) ? current : [...current, productId],
      );
      const product = productById(productId);
      if (product) notify(active ? `Removed ${product.name} from wishlist` : `Saved ${product.name} to wishlist`);
    },
    [wishlist, notify],
  );

  const value = useMemo<ShopState>(() => {
    const lines: ResolvedLine[] = cart.flatMap((line) => {
      const product = productById(line.productId);
      return product ? [{ ...line, product, lineTotal: Number(product.price) * line.qty }] : [];
    });
    const subtotal = lines.reduce((sum, line) => sum + line.lineTotal, 0);
    const shipping = subtotal === 0 || subtotal >= FREE_SHIPPING_THRESHOLD ? 0 : FLAT_SHIPPING;
    return {
      lines,
      cartCount: lines.reduce((sum, line) => sum + line.qty, 0),
      subtotal,
      shipping,
      total: subtotal + shipping,
      wishlist,
      toasts,
      addToCart,
      setQty,
      removeFromCart,
      clearCart,
      toggleWishlist,
      isWishlisted: (productId: string) => wishlist.includes(productId),
      notify,
    };
  }, [cart, wishlist, toasts, addToCart, setQty, removeFromCart, clearCart, toggleWishlist, notify]);

  return <ShopContext.Provider value={value}>{children}</ShopContext.Provider>;
}

export function useShop(): ShopState {
  const ctx = useContext(ShopContext);
  if (!ctx) throw new Error("useShop must be used within <ShopProvider>");
  return ctx;
}
