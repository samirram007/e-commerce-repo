import { useEffect } from "react";
import { createFileRoute, Link, Outlet, redirect, useNavigate, useRouterState } from "@tanstack/react-router";
import { SheetSelect } from "../components/sheet";
import { ProfileMenu } from "../components/profile-menu";
import { FiscalYearPicker } from "../features/periods/FiscalYearPicker";
import { useAuth, ensureSession } from "../auth/auth-context";

/**
 * Pathless layout wrapping every authenticated screen. Runs an auth guard in
 * `beforeLoad` (restoring the session from the refresh cookie on hard reload)
 * and renders the application shell: sidebar, topbar, company switcher, outlet.
 */
export const Route = createFileRoute("/_protected")({
  beforeLoad: async () => {
    const ok = await ensureSession();
    if (!ok) {
      throw redirect({ to: "/login" });
    }
  },
  component: ProtectedLayout,
});

type AppPath =
  | "/"
  | "/products"
  | "/partners"
  | "/orders"
  | "/shipments"
  | "/returns"
  | "/purchase-orders"
  | "/inventory"
  | "/invoices"
  | "/payments"
  | "/accounting"
  | "/reports"
  | "/audit"
  | "/payroll"
  | "/users"
  | "/roles"
  | "/setup"
  | "/settings";

interface NavItem {
  to: AppPath;
  label: string;
  /** Hidden unless the user holds this permission (admins always pass). */
  permission?: string;
}

const NAV_LINKS: NavItem[] = [
  { to: "/", label: "Dashboard" },
  { to: "/products", label: "Catalog", permission: "catalog.view" },
  { to: "/partners", label: "Customers & Vendors" },
  { to: "/orders", label: "Sales Orders", permission: "sales.view" },
  { to: "/shipments", label: "Shipments" },
  { to: "/returns", label: "Returns" },
  { to: "/purchase-orders", label: "Purchasing", permission: "purchasing.view" },
  { to: "/inventory", label: "Inventory", permission: "inventory.view" },
  { to: "/invoices", label: "Invoices", permission: "invoicing.view" },
  { to: "/payments", label: "Payments", permission: "payments.view" },
  { to: "/accounting", label: "Accounting", permission: "accounting.journal.view" },
  { to: "/reports", label: "Reports", permission: "reports.view" },
  { to: "/audit", label: "Audit Log", permission: "audit.log.read" },
  { to: "/payroll", label: "Payroll", permission: "payroll.view" },
  { to: "/users", label: "Users", permission: "platform.users.manage" },
  { to: "/roles", label: "Roles", permission: "platform.users.manage" },
  { to: "/setup", label: "Setup", permission: "company.settings.manage" },
  { to: "/settings", label: "Settings", permission: "company.settings.manage" },
];

function Sidebar(): React.JSX.Element {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const { hasPermission } = useAuth();
  const links = NAV_LINKS.filter((item) => !item.permission || hasPermission(item.permission));

  return (
    <nav className="sidebar">
      <div className="brand">ERP</div>
      {links.map((item) => (
        <Link key={item.to} to={item.to} className={pathname === item.to ? "active" : ""}>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

function CompanySwitcher(): React.JSX.Element | null {
  const { companies, companyId, switchCompany } = useAuth();
  if (companies.length === 0) return null;

  return (
    <SheetSelect
      value={companyId ?? companies[0]?.id ?? ""}
      options={companies.map((company) => ({ value: company.id, label: company.name }))}
      onChange={(value) => switchCompany(value)}
      placeholder="Select company"
      title="Switch company"
      searchPlaceholder="Search companies…"
      className="company-switcher"
    />
  );
}

function Topbar(): React.JSX.Element {
  return (
    <div className="topbar">
      <div className="topbar-filters">
        <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          Company: <CompanySwitcher />
        </div>
        <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          Fiscal year: <FiscalYearPicker />
        </div>
      </div>
      <ProfileMenu />
    </div>
  );
}

function ProtectedLayout(): React.JSX.Element {
  const { isAuthenticated, status } = useAuth();
  const navigate = useNavigate();

  // Session can lapse mid-visit (token expiry / logout elsewhere).
  useEffect(() => {
    if (status === "guest") {
      void navigate({ to: "/login" });
    }
  }, [status, navigate]);

  if (!isAuthenticated) {
    return <div className="login-wrap muted">Loading…</div>;
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="content">
        <Topbar />
        <Outlet />
      </div>
    </div>
  );
}
