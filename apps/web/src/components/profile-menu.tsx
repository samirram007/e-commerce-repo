import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Badge } from "./ui";
import { useAuth } from "../auth/auth-context";
import { useTheme } from "../theme/theme-context";
import { titleCase } from "../lib/format";
import { cn } from "../lib/utils";

/**
 * Account menu shown in the app-shell topbar. The trigger reveals the signed-in
 * user plus the account-related destinations they are allowed to reach
 * (settings, users, roles, audit) and the sign-out action.
 */
interface ProfileLink {
  to: "/settings" | "/users" | "/roles" | "/audit";
  label: string;
  /** Hidden unless the user holds this permission (admins always pass). */
  permission?: string;
}

const PROFILE_LINKS: ProfileLink[] = [
  { to: "/settings", label: "Company settings", permission: "company.settings.manage" },
  { to: "/users", label: "Users", permission: "platform.users.manage" },
  { to: "/roles", label: "Roles & permissions", permission: "platform.users.manage" },
  { to: "/audit", label: "Audit log", permission: "audit.log.read" },
];

/** How many role chips to show in the menu header before collapsing to "+N". */
const MAX_ROLE_BADGES = 3;

function initials(name: string | null | undefined, email: string | null | undefined): string {
  const source = (name ?? "").trim() || (email ?? "").trim();
  if (!source) return "?";
  const parts = source
    .replace(/@.*$/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);
  const letters = parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("");
  return (letters || source[0]).toUpperCase();
}

export function ProfileMenu(): React.JSX.Element {
  const { user, roles, isPlatformAdmin, isCompanyAdmin, hasPermission, logout } = useAuth();
  const { theme, cycleTheme } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const displayName = user?.full_name?.trim() || user?.email || "Account";
  const links = PROFILE_LINKS.filter((link) => !link.permission || hasPermission(link.permission));

  // Dedupe case-insensitively (the platform admin holds every role, so the raw
  // list contains overlapping labels) and keep the header compact.
  const seenRoles = new Set<string>();
  const allRoleBadges: string[] = [];
  for (const label of [
    isPlatformAdmin ? "Platform admin" : null,
    isCompanyAdmin ? "Company admin" : null,
    ...roles.map((role) => titleCase(role)),
  ]) {
    if (!label) continue;
    const key = label.toLowerCase();
    if (seenRoles.has(key)) continue;
    seenRoles.add(key);
    allRoleBadges.push(label);
  }
  const roleBadges = allRoleBadges.slice(0, MAX_ROLE_BADGES);
  const hiddenRoleCount = allRoleBadges.length - roleBadges.length;

  return (
    <div className="profile-menu" ref={containerRef}>
      <button
        type="button"
        className={cn("profile-trigger", open && "open")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="avatar" aria-hidden="true">
          {initials(user?.full_name, user?.email)}
        </span>
        <span className="profile-trigger-text">
          <span className="profile-name">{displayName}</span>
          <span className="muted">{user?.email}</span>
        </span>
        <span className="chevron" aria-hidden="true">
          ▾
        </span>
      </button>

      {open ? (
        <div className="menu" role="menu" aria-label="Account menu">
          <div className="menu-header">
            <span className="avatar lg" aria-hidden="true">
              {initials(user?.full_name, user?.email)}
            </span>
            <div className="menu-header-text">
              <div className="menu-name">{user?.full_name?.trim() || displayName}</div>
              <div className="muted">{user?.email}</div>
              {roleBadges.length > 0 ? (
                <div className="menu-roles">
                  {roleBadges.map((label) => (
                    <Badge key={label}>{label}</Badge>
                  ))}
                  {hiddenRoleCount > 0 ? <Badge>+{hiddenRoleCount} more</Badge> : null}
                </div>
              ) : null}
            </div>
          </div>

          {links.length > 0 ? (
            <>
              <div className="menu-divider" />
              {links.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  role="menuitem"
                  className="menu-item"
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
            </>
          ) : null}

          <div className="menu-divider" />
          <button
            type="button"
            role="menuitem"
            className="menu-item"
            onClick={cycleTheme}
          >
            Theme: {theme === "system" ? "Follow system" : titleCase(theme)}
          </button>

          <div className="menu-divider" />
          <button
            type="button"
            role="menuitem"
            className="menu-item menu-danger"
            onClick={() => {
              setOpen(false);
              void logout().finally(() => navigate({ to: "/login" }));
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
