import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { ensureSession } from "../auth/auth-context";

/**
 * Pathless layout for unauthenticated screens (sign-in, first-time setup).
 * Attempts a silent session restore first, so a valid refresh cookie takes the
 * visitor straight into the app instead of showing the sign-in form.
 */
export const Route = createFileRoute("/_guest")({
  beforeLoad: async () => {
    const ok = await ensureSession();
    if (ok) {
<<<<<<< HEAD
      throw redirect({ to: "/shop" });
=======
      throw redirect({ to: "/dashboard" });
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
    }
  },
  component: GuestLayout,
});

function GuestLayout(): React.JSX.Element {
  return (
    <div className="guest-shell">
      <Outlet />
    </div>
  );
}
