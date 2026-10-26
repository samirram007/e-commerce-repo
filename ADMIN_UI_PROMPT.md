# Task: Scaffold a separate `apps/admin/` app (TanStack Router) with login + protected routes

You are working in a monorepo with `apps/api/` (FastAPI) and `apps/web/` (the storefront + current
ERP screens). **Read `AGENTS.md` and `AGENT.md` first and follow them.** Create a new, independent
admin app in **`apps/admin/`** (the root `pnpm-workspace.yaml` already globs `apps/*`, so a new
folder there is picked up automatically). Do **not** modify `apps/web/` in this task, except
to read it for reference.

## Stack — match `apps/web/package.json` exactly (same major versions)

- [ ] React 19 + strict TypeScript, Vite 8, `@vitejs/plugin-react`, Tailwind 4 via `@tailwindcss/vite`.
  (`AGENTS.md` says React 18, but `apps/web/package.json` is on 19, so use 19.)
- [ ] `@tanstack/react-router` + `@tanstack/router-plugin` (**file-based routing**), `@tanstack/react-query`,
  Axios, zod 4, `react-aria-components`, `lucide-react`, `clsx` + `tailwind-merge`, vitest.
- [ ] **pnpm only**: copy `apps/web/scripts/ensure-pnpm.mjs` and add the `preinstall` guard.
  `packageManager`/`engines` are pinned in the **root** `package.json` and the single
  `pnpm-lock.yaml` lives at the repo root — run `pnpm install` there and commit the updated lockfile.
- [ ] Scripts: `dev`, `build` (`vite build && tsc -b`), `preview`, `test` (`vitest run`), `typecheck`.
- [ ] `vite.config.ts`: same `tanstackRouter({ target: "react", autoCodeSplitting: true, routesDirectory: "./src/routes", generatedRouteTree: "./src/routeTree.gen.ts" })`, `@` → `src` alias,
  **port 5174**, and a proxy `/api` → `VITE_API_PROXY ?? "http://127.0.0.1:8000"` (use IPv4, as `apps/web/` does).
- [ ] Don't hand-edit `routeTree.gen.ts`.

## Backend contract (already exists — do not change the backend's auth behavior)

- `POST /api/v1/auth/login` with `{ email, password }` → `{ access_token, expires_in, user }`,
  and sets an **httpOnly `refresh_token` cookie** (path `/api/v1/auth`, SameSite=Lax).
- `POST /api/v1/auth/refresh` (cookie) → a new `LoginOut`. `POST /api/v1/auth/logout` (cookie) → 204.
- `GET /api/v1/auth/me` → `{ user, companies[], permissions[], is_company_admin, roles[] }`.
- Company scoping uses the `X-Company-Id` header. The backend is authoritative.
- Errors use the envelope `{ "error": { code, message, details } }`.
- Backend CORS allows only `http://localhost:5173` (`app/core/config.py` `cors_origins`). Dev
  traffic goes through the Vite proxy, so CORS doesn't matter in dev. Add `http://localhost:5174` to
  the default `cors_origins` anyway and note it. This is the **only** backend change allowed.

## Auth layer (port the patterns from `apps/web/src/auth` and `apps/web/src/lib`; don't import across apps)

- `src/lib/api-client.ts`: Axios with `baseURL: "/api/v1"`, `withCredentials: true`, a bearer token +
  `X-Company-Id` interceptor, and **single-flight refresh on 401** with one retry. It rejects with `ApiError`.
- `src/lib/error-handling.ts`: `ApiError` parsed from the envelope, plus a network-error constant.
- `src/lib/query-client.ts`: shared `QueryClient` defaults and `clearSensitiveCaches()`.
- `src/auth/session-store.ts`: a `useSyncExternalStore` store. Keep the access token **in memory only**
  (never localStorage). It may persist the selected `companyId` only.
- `src/auth/auth-context.tsx`: `AuthProvider` + `useAuth()` exposing `isAuthenticated`, `user`,
  `companies`, `permissions`, `roles`, `isAdmin`, `hasPermission`, `hasRole`, `login`, `logout`,
  `switchCompany`, plus a non-React `ensureSession()` that restores the session on reload by calling
  `/auth/refresh` and then `/auth/me`. `ensureSession()` is used by route `beforeLoad`.
- `src/auth/guards.tsx`: `RequirePermission` and `RequireRole` for in-page gating.
- Logout calls `/auth/logout`, clears the session and `clearSensitiveCaches()`, then navigates to `/login`.
  A company switch does a full `window.location.reload()` so no cache from the old company leaks.

## Routes (`src/routes/`, file-based)

- `__root.tsx`: `QueryClientProvider` + `AuthProvider`, `<Outlet/>`, a 404 `notFoundComponent`, and an error boundary.
  Use `createRootRouteWithContext<{ queryClient; auth }>()`.
- `_guest.tsx`: a pathless layout. Its `beforeLoad` redirects already-signed-in users to `search.redirect ?? "/"`.

  - `_guest/login.tsx` → `/login`:
    - email + password form, validated with zod
    - submit disabled while pending
    - shows the backend error message (e.g. invalid credentials) inline
    - show/hide password toggle
    - accessible labels; Enter submits
    - validated `redirect` search param, accepting **only same-origin relative paths** (no open redirect)
    - on success, navigate to the redirect or `/`
- `_protected.tsx`: a pathless layout. Its `beforeLoad` runs `await ensureSession()` and, if there's
  no session, `throw redirect({ to: "/login", search: { redirect: location.href } })`. It renders the
  app shell:

  - a collapsible sidebar, filtered by permission
  - a topbar with a company switcher (a `SheetSelect`) and a profile menu with logout
  - mobile drawer behavior
- `_protected/index.tsx` → `/`: a dashboard placeholder with a welcome message and the current company.
- `_protected/profile.tsx` → `/profile`: shows `/auth/me` data.
- `_protected/forbidden.tsx` → `/forbidden`.
- Add placeholder routes for the admin sections the next tasks will fill in, each gated by its
  permission (the names come from `apps/api/app/core/permissions.py`, so look them up; don't invent them):

  - `products`
  - `categories`
  - `orders`
  - `customers`
  - `storefront` (content: hero, FAQs, policies)
  - `users`
  - `roles`
  - `settings`

  Each section has a typed `beforeLoad` check that redirects to `/forbidden`. Keep one nav config
  array (`src/config/nav.ts`: label, icon, path, permission) as the single source of truth for both
  the sidebar and the route checks.

## UI conventions (same as `apps/web/`)

- Put shared primitives in `src/components/`: `ui.tsx` (Button, Input, Card, etc.), plus `sheet.tsx`
  with a **`SheetSelect`** (a searchable slide-over). **Never use a native `<select>`.**
- Put feature code in `src/features/<module>/` (`schemas.ts` zod, `api.ts`, `queries.ts`
  with `queryOptions`, `<Name>Page.tsx`).
- Support light and dark themes with Tailwind tokens.
- Show a loading state while `ensureSession` runs, so there's no flash of the login page.
- Money values from the API are decimal strings. Never do float math on them.

## Infra & docs

- `apps/admin/.env.example` (`VITE_API_PROXY`), `apps/admin/README.md` (setup, scripts, route map, auth flow).
- Add an `admin` service to `docker-compose.yml` mirroring `web` (port 5174). Note that there's still
  no Dockerfile, consistent with the current repo state.
- Update root `AGENTS.md`:
  - add `apps/admin/` to Layout
  - add its commands and route structure
- `.gitignore`: `apps/admin/node_modules`, `apps/admin/dist`.

## Tests & verification

- Add a vitest config with jsdom + Testing Library. Write tests for:
  - redirect-param sanitizing
  - the `_protected` redirect when there's no session
  - the login form's validation and error display (mock Axios)
  - `hasPermission`
- Each must exit 0:
  - `corepack enable && pnpm install` (at the repo root)
  - `pnpm build` / `pnpm test` from `apps/admin/`, or from the root as
    `pnpm build --filter=<admin package name>`
- Manually, with the backend running (`uv run uvicorn app.main:app --reload`) and the seed loaded
  (`uv run python -m app.seed`), run `pnpm dev`. Check that:
  - `/` redirects to `/login?redirect=…`
  - the seeded admin can log in and lands on the redirect target
  - a reload keeps the session (refresh cookie)
  - logout returns to `/login`
  - a user without a permission gets `/forbidden`

## Deliverable

Small commits: scaffold → auth layer → routes/shell → tests → docs/compose. Then report:

- the file tree
- the route map
- the commands you ran and their output
- every deviation from this prompt, with the reason
