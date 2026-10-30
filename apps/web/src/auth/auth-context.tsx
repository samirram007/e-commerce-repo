/**
 * Auth context: the single source of truth for "who is signed in, for which
 * company, and what may they do".
 *
 * State lives in `session-store` (a `useSyncExternalStore` store) so it is also
 * readable outside React — `ensureSession()` is used by route `beforeLoad`
 * guards, which cannot use hooks. `AuthProvider` exposes the same state plus
 * role/permission predicates to components via `useAuth()`.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { clearSensitiveCaches } from "../lib/query-client";
import { getAccessToken } from "./session";
import { getSession, setSession, useSession } from "./session-store";
import { identityApi } from "../services/identity-helpers";
import type { CompanySummary, MeOut, UserOut } from "../services/identity";

export type AuthStatus = "unknown" | "authenticating" | "authenticated" | "guest";

/** Roles that confer broad ("admin") access regardless of the company-admin flag. */
const ADMIN_ROLES = ["admin", "developer"] as const;

export interface AuthContextValue {
  status: AuthStatus;
  user: UserOut | null;
  me: MeOut | null;
  companies: CompanySummary[];
  companyId: string | null;

  /** Permission keys granted for the active company ("*" means everything). */
  permissions: string[];
  /** Assignable role names held for the active company. */
  roles: string[];

  isAuthenticated: boolean;
  isPlatformAdmin: boolean;
  isCompanyAdmin: boolean;
  isDeveloper: boolean;
  /** True for platform/company admins and the `admin`/`developer` tiers. */
  isAdmin: boolean;

  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (...permissions: string[]) => boolean;
  hasRole: (...roles: string[]) => boolean;

  login: (email: string, password: string) => Promise<void>;
  bootstrap: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  switchCompany: (companyId: string) => void;
  /** Re-fetch `/auth/me`; returns false when the session is no longer valid. */
  refresh: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

let inflightEnsure: Promise<boolean> | null = null;

/**
 * Restore (or confirm) the session without React — safe to call from route
 * `beforeLoad`. Returns true when an authenticated session is available.
 */
export async function ensureSession(): Promise<boolean> {
  const current = getSession();
  if (current.status === "authenticated" && current.me) return true;
  if (inflightEnsure) return inflightEnsure;

  inflightEnsure = (async () => {
    setSession({ status: "authenticating" });
    try {
      // No in-memory token (hard reload): try the httpOnly refresh cookie.
      if (!getAccessToken()) {
        const token = await identityApi.tryRefreshToken();
        if (!token) {
          setSession({ me: null, status: "guest" });
          return false;
        }
      }
      const profile = await identityApi.refreshMe();
      if (!profile) {
        setSession({ me: null, status: "guest" });
        return false;
      }
      const previousCompany = getSession().companyId;
      setSession({
        me: profile,
        companyId: previousCompany ?? profile.companies[0]?.id ?? null,
        status: "authenticated",
      });
      return true;
    } catch {
      setSession({ me: null, status: "guest" });
      return false;
    } finally {
      inflightEnsure = null;
    }
  })();

  return inflightEnsure;
}

function can(permissions: readonly string[], needed: string): boolean {
  return permissions.includes("*") || permissions.includes(needed);
}

export function AuthProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const session = useSession();
  const me = session.me;

  // Restore a session once on mount (covers hard reloads on any route).
  useEffect(() => {
    if (getSession().status === "unknown") {
      void ensureSession();
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await identityApi.login(email, password);
  }, []);

  const bootstrap = useCallback(async (email: string, password: string, fullName: string) => {
    await identityApi.bootstrap(email, password, fullName);
  }, []);

  const logout = useCallback(async () => {
    await identityApi.logout();
    clearSensitiveCaches();
    setSession({ me: null, status: "guest" });
    window.location.href = "/login";
  }, []);

  const switchCompany = useCallback((companyId: string) => {
    if (companyId === getSession().companyId) return;
    // Company switch invalidates every company-scoped cache; reload to avoid
    // stale cross-company data.
    clearSensitiveCaches();
    setSession({ companyId });
    window.location.reload();
  }, []);

  const refresh = useCallback(async () => {
    const profile = await identityApi.refreshMe();
    if (!profile) {
      setSession({ me: null, status: "guest" });
      return false;
    }
    setSession({
      me: profile,
      companyId: getSession().companyId ?? profile.companies[0]?.id ?? null,
      status: "authenticated",
    });
    return true;
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const permissions = me?.permissions ?? [];
    const roles = me?.roles ?? [];
    const isPlatformAdmin = Boolean(me?.user.is_platform_admin);
    const isCompanyAdmin = Boolean(me?.is_company_admin);
    const isDeveloper = isPlatformAdmin || roles.includes("developer");
    const isAdmin =
      isDeveloper ||
      isCompanyAdmin ||
      permissions.includes("*") ||
      ADMIN_ROLES.some((role) => roles.includes(role));

    return {
      status: session.status,
      user: me?.user ?? null,
      me,
      companies: me?.companies ?? [],
      companyId: session.companyId,
      permissions,
      roles,
      isAuthenticated: session.status === "authenticated" && me !== null,
      isPlatformAdmin,
      isCompanyAdmin,
      isDeveloper,
      isAdmin,
      hasPermission: (permission) => can(permissions, permission),
      hasAnyPermission: (...needed) => needed.some((permission) => can(permissions, permission)),
      hasRole: (...needed) =>
        needed.length === 0 ||
        isPlatformAdmin ||
        isCompanyAdmin ||
        needed.some((role) => roles.includes(role)),
      login,
      bootstrap,
      logout,
      switchCompany,
      refresh,
    };
  }, [session.companyId, session.status, me, login, bootstrap, logout, switchCompany, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
