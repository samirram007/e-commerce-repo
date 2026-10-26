import { createFileRoute, redirect } from "@tanstack/react-router";
import { ensureSession } from "../auth/auth-context";
import { unmatchedPathTarget } from "../lib/redirect";

/**
 * Catch-all for unknown URLs.
 *
 * Guests are not bounced to the login screen any more: an unknown shop link
 * (or a stale bookmark) lands on the public storefront, while a signed-in user
 * goes back to the app shell.
 */
export const Route = createFileRoute("/$")({
  beforeLoad: async () => {
    const isAuthenticated = await ensureSession();
    throw redirect({ to: unmatchedPathTarget(isAuthenticated) });
  },
});
