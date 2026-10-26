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
  | "/dashboard"
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

interface NavGroup {
  /** Section header; groups without a label render their links unheaded. */
  label?: string;
  links: NavItem[];
}

/**
 * Sidebar sections, mirrored by domain so related screens stay together.
 * A whole group is hidden when the user lacks every permission it requires.
 */
const NAV_GROUPS: NavGroup[] = [
  {
    links: [{ to: "/dashboard", label: "Dashboard" }],
  },
  {
    label: "Sales",
    links: [
      { to: "/orders", label: "Sales Orders", permission: "sales.view" },
      { to: "/shipments", label: "Shipments" },
      { to: "/returns", label: "Returns" },
    ],
  },
  {
    label: "Supply",
    links: [
      { to: "/products", label: "Catalog", permission: "catalog.view" },
      { to: "/partners", label: "Customers & Vendors" },
      { to: "/purchase-orders", label: "Purchasing", permission: "purchasing.view" },
      { to: "/inventory", label: "Inventory", permission: "inventory.view" },
    ],
  },
  {
    label: "Finance",
    links: [
      { to: "/invoices", label: "Invoices", permission: "invoicing.view" },
      { to: "/payments", label: "Payments", permission: "payments.view" },
      { to: "/accounting", label: "Accounting", permission: "accounting.journal.view" },
      { to: "/reports", label: "Reports", permission: "reports.view" },
      { to: "/payroll", label: "Payroll", permission: "payroll.view" },
    ],
  },
  {
    label: "Administration",
    links: [
      { to: "/users", label: "Users", permission: "platform.users.manage" },
      { to: "/roles", label: "Roles", permission: "platform.users.manage" },
      { to: "/audit", label: "Audit Log", permission: "audit.log.read" },
      { to: "/setup", label: "Setup", permission: "company.settings.manage" },
      { to: "/settings", label: "Settings", permission: "company.settings.manage" },
    ],
  },
];

function Sidebar(): React.JSX.Element {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const { hasPermission } = useAuth();

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links.filter((item) => !item.permission || hasPermission(item.permission)),
  })).filter((group) => group.links.length > 0);

  return (
    <nav className="sidebar">
      <div className="brand">ERP</div>
      {visibleGroups.map((group, index) => (
        group.label === undefined ? (
          <div className="nav-ungrouped" key={index}>
            {group.links.map((item) => (
              <Link key={item.to} to={item.to} className={pathname === item.to ? "active" : ""}>
                {item.label}
              </Link>
            ))}
          </div>
        ) : (
          <div className="nav-group" key={index}>
            <div className="nav-group-label">{group.label}</div>
            {group.links.map((item) => (
              <Link key={item.to} to={item.to} className={pathname === item.to ? "active" : ""}>
                {item.label}
              </Link>
            ))}
          </div>
        )
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
