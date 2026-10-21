/**
 * Guest shopper identity for the public storefront.
 *
 * The store works without an account: a stable cart token identifies the
 * browser's cart, and an anonymous id scopes favorites/watchlist. Both are
 * persisted in localStorage so a reload keeps the cart. When the shopper signs
 * in to the ERP the backend prefers the user id over the anonymous id.
 */

const CART_TOKEN_KEY = "shop.cartToken";
const ANON_ID_KEY = "shop.anonId";
const COMPANY_ID_KEY = "shop.companyId";

/** Slug of the storefront to open; overridable per deployment. */
export const STOREFRONT_SLUG: string =
  (import.meta.env.VITE_STOREFRONT_SLUG as string | undefined) ?? "default";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private mode / storage disabled
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore: the session simply won't survive a reload
  }
}

function randomId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Stable per-browser cart token (>= 8 chars, as the backend requires). */
export function cartToken(): string {
  const existing = read(CART_TOKEN_KEY);
  if (existing) return existing;
  const token = `cart_${randomId()}`;
  write(CART_TOKEN_KEY, token);
  return token;
}

/** Stable per-browser anonymous id used for favorites/watchlist. */
export function anonId(): string {
  const existing = read(ANON_ID_KEY);
  if (existing) return existing;
  const id = `anon_${randomId()}`;
  write(ANON_ID_KEY, id);
  return id;
}

/** Company the shopper is browsing (resolved from the store slug). */
export function cachedCompanyId(): string | null {
  return read(COMPANY_ID_KEY);
}

export function setCachedCompanyId(companyId: string): void {
  write(COMPANY_ID_KEY, companyId);
}
