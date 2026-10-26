import { createRootRoute, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";
import { AuthProvider, useAuth } from "../auth/auth-context";
import { ThemeProvider, useTheme } from "../theme/theme-context";

/**
 * Root route: installs the auth + theme providers (query client lives in `main.tsx`)
 * and renders the matched child. Auth guarding happens in the pathless
 * `_guest` / `_protected` layouts.
 */
export const Route = createRootRoute({ component: RootLayout });

/** Loads the user's server-side preferences once they are signed in. */
function ThemePreferencesLoader(): React.JSX.Element | null {
  const { isAuthenticated } = useAuth();
  const { syncFromServer } = useTheme();
  useEffect(() => {
    if (isAuthenticated) void syncFromServer();
  }, [isAuthenticated, syncFromServer]);
  return null;
}

function RootLayout(): React.JSX.Element {
  return (
    <AuthProvider>
      <ThemeProvider>
        <ThemePreferencesLoader />
        <Outlet />
      </ThemeProvider>
    </AuthProvider>
  );
}
