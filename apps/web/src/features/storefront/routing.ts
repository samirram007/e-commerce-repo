/** Routing helpers for the public storefront (pure, unit-tested). */

/** Sign-in URL that returns the shopper to the shop page they were on. */
export function shopSignInHref(locationHref: string): string {
  const href = locationHref.startsWith("/") ? locationHref : "/shop";
  return `/login?redirect=${encodeURIComponent(href)}`;
}
