import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AuthProvider } from "../auth/auth-context";

export const Route = createFileRoute("/_admin")({
  component: () => {
    return (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    );
  },
});