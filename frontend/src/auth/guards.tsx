/**
 * Declarative role/permission guards for gating UI (buttons, panels, routes).
 *
 * These complement the server-side enforcement (which is authoritative); they
 * only decide what to render. Route-level auth gating lives in the
 * `_guest`/`_protected` layouts.
 */
import type { ReactNode } from "react";
import { EmptyState } from "../components/ui";
import { useAuth } from "./auth-context";

export function AccessDenied({
  title = "Access denied",
  message = "You do not have permission to view this.",
}: {
  title?: string;
  message?: string;
}) {
  return <EmptyState title={title} message={message} />;
}

export function RequireAuth({
  children,
  fallback = null,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <>{fallback}</>;
}

export function RequirePermission({
  permission,
  children,
  fallback = <AccessDenied />,
}: {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { hasPermission } = useAuth();
  return hasPermission(permission) ? <>{children}</> : <>{fallback}</>;
}

export function RequireAnyPermission({
  permissions,
  children,
  fallback = <AccessDenied />,
}: {
  permissions: string[];
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { hasAnyPermission } = useAuth();
  return hasAnyPermission(...permissions) ? <>{children}</> : <>{fallback}</>;
}

/** Role-based guard (platform/company admins always pass). */
export function RequireRole({
  roles,
  children,
  fallback = <AccessDenied />,
}: {
  roles: string[];
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { hasRole } = useAuth();
  return hasRole(...roles) ? <>{children}</> : <>{fallback}</>;
}

/** Broad admin gate: platform admin, company admin, or admin/developer role. */
export function RequireAdmin({
  children,
  fallback = <AccessDenied />,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { isAdmin } = useAuth();
  return isAdmin ? <>{children}</> : <>{fallback}</>;
}
