/**
 * Navigation targets that are easy to get wrong — kept pure and unit-tested.
 */

/** Fallback for a signed-in visitor whose URL matched no route. */
const AUTHED_HOME = "/dashboard";
/** Fallback for a guest whose URL matched no route: the public storefront home. */
const GUEST_HOME = "/";

/**
 * Post-login target from `?redirect=`.
 *
 * Only same-origin absolute app paths are allowed: `//host` and `/\host` are
 * protocol-relative URLs, and anything without a leading `/` would leave the
 * app entirely.
 */
export function safeRedirect(value: string | undefined | null): string {
  if (!value) return AUTHED_HOME;
  if (!value.startsWith("/")) return AUTHED_HOME;
  // `//evil.com` and `/\evil.com` (backslash is treated as `/` by browsers).
  if (value.startsWith("//") || value.startsWith("/\\")) return AUTHED_HOME;
  // Whitespace / control characters can smuggle a different target.
  if (/[\s\u0000-\u001f]/.test(value)) return AUTHED_HOME;
  return value;
}

/** Where an unmatched URL should send the visitor. */
export function unmatchedPathTarget(isAuthenticated: boolean): string {
  return isAuthenticated ? AUTHED_HOME : GUEST_HOME;
}
