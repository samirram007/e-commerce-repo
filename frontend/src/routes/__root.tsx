import { createRootRoute, Outlet } from "@tanstack/react-router";
import { AuthProvider } from "../auth/auth-context";

/**
 * Root route: installs the auth provider (query client lives in `main.tsx`) and
 * renders the matched child. Auth guarding happens in the pathless
 * `_guest` / `_protected` layouts.
 */
export const Route = createRootRoute({ component: RootLayout });

function RootLayout(): React.JSX.Element {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}
