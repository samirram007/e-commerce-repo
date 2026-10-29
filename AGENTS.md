# AGENTS.md

Quick operational guide for agents. The detailed, authoritative project spec is
in **`AGENT.md`** (read it before implementing features). This file only records
repo-specific facts that are easy to get wrong.

## Layout

**Turborepo + pnpm workspace** — root `package.json` (`turbo` devDependency + `packageManager`
pin), `pnpm-workspace.yaml` (`packages: ["apps/*"]`), `turbo.json` (tasks `build`, `dev`, `test`,
`migrate`). Install from the repo root; the single `pnpm-lock.yaml` lives at the root.

- `apps/api/` — FastAPI + SQLAlchemy 2.x + Alembic, Python 3.12, managed by `uv` (npm package `erp-backend`, scripts shell out to `uv`).
- `apps/web/` — React 18 + strict TypeScript + Vite, TanStack Router/Query, Axios (npm package `erp-frontend`).
- `docker-compose.yml` (root) — postgres 16, redis 7, `api`, `web` (build contexts `./apps/api`, `./apps/web`).

## Commands

Root (Turborepo orchestrates both apps):

- `pnpm install` — install workspace deps from the repo root (do not use npm; the `preinstall` guard still blocks it).
- `pnpm dev` — `turbo run dev`: uvicorn `:8000` + Vite `:5173` concurrently.
- `pnpm build` — `turbo run build`: frontend `vite build && tsc -b` (the backend has no build
  step — `uv run` syncs `apps/api/.venv` on demand).
- `pnpm test` — `turbo run test`: `uv run pytest` and `vitest run`.
- `pnpm migrate` — `turbo run migrate`: `uv run alembic upgrade head` (never cached).
- Scope with `--filter`: package names are `erp-backend` / `erp-frontend`, e.g. `pnpm build --filter=erp-frontend`.

Backend (run from `apps/api/`):

- `uv sync` — install deps (`.venv/` already present).

* [ ] - 

- `uv run pytest tests/test_accounting_invariants.py::test_unbalanced_journal_rejected` — single test.
- `uv run alembic upgrade head` — migrate (reads `DATABASE_URL`; `ALEMBIC_DATABASE_URL` overrides).
- `uv run alembic revision --autogenerate -m "..."` — new revision.
- `uv run uvicorn app.main:app --reload` — dev server (`:8000`).
- `uv run python -m app.seed` — idempotent seed: admin + demo company/chart/warehouse.
- No backend lint/format/typecheck tool is configured. `.gitignore` mentions `.ruff_cache`/`.mypy_cache` but neither is wired up.

Frontend (run from `apps/web/`, or from root with `pnpm --filter erp-frontend <script>`) —
**pnpm only** (npm/yarn are blocked by the `preinstall` guard in `scripts/ensure-pnpm.mjs`;
`packageManager` pins pnpm at the root):

- `pnpm install` — workspace install happens at the repo root (`pnpm-lock.yaml` at root; do not use npm).
- `pnpm dev` — Vite `:5173`, proxies `/api` → `VITE_API_PROXY ?? http://localhost:8000`.
- `pnpm build` — `vite build && tsc -b` (vite regenerates `routeTree.gen.ts`, then tsc typechecks).

## Current state (verify before assuming these still hold)

- Routing is file-based under `src/routes/` (see below), not the old `src/routes.tsx`.
- **`pnpm build` fails (pre-existing, NOT caused by the Turborepo layout — verified by running
  `pnpm build` on an untouched HEAD worktree): the TanStack router generator aborts with
  `Conflicting configuration paths … "/"` between `src/routes/_admin.tsx` and
  `src/routes/_shop/index.tsx`, so `routeTree.gen.ts` is never regenerated and `tsc -b` then
  errors `src/routes/_admin.tsx(4,38): TS2345 "…/_admin" not assignable to keyof FileRoutesByPath`.
  Fix the route conflict, then let vite regenerate `routeTree.gen.ts`.
- `pnpm test` passes (**verified** through turbo): `vitest run` → 8 tests in
  `src/hooks/use-list-state.test.ts`; `uv run pytest` → 114 tests.
- Backend tests pass (114 tests, incl. `tests/test_payment_gateways.py`). `tests/conftest.py` builds the schema with
  `Base.metadata.create_all`, **not** Alembic, and overrides env vars before app import.
- There are **11** Alembic revisions in `apps/api/migrations/versions/` (head:
  `b3f7d21a9c04_payment_gateway_configs.py`); `649d352f339d` added `blamable`
  to 25 tables.
- `psycopg[binary]` is a dependency on **all platforms now** (the old
  `platform_system != 'Windows'` marker was removed), so Windows dev can target Postgres.
  `httpx` moved into the **main** dependencies (payment gateway adapters call
  Razorpay/Stripe REST APIs); `cryptography` was added for Fernet secret encryption.
  With no `DATABASE_URL`, the code default is still `sqlite:///./erp_dev.db`.
- `apps/api/.env` may point at a **local PostgreSQL** (this machine runs the
  `postgresql-x64-18` Windows service, not docker-compose). If the password contains
  URL-reserved characters (`@`, `:`, `/`, `%`), percent-encode them in the URL (e.g. `@` →
  `%40`); `migrations/env.py` escapes `%` for Alembic's ConfigParser interpolation.
- **SQLite tests do not enforce `VARCHAR` length** (or other dialect constraints); Postgres
  does. Postgres-only bugs (e.g. a string too long for a sized column) will **not** appear in
  `uv run pytest` — run the API against Postgres for real end-to-end confidence.
- Neither `apps/api/` nor `apps/web/` has a `Dockerfile`, although `docker-compose.yml`
  declares `build:` contexts for both — so `docker compose build` cannot succeed as-is.

## Backend architecture (non-obvious)

- Modules live in `app/modules/<name>/` with `router.py`, `service.py`, `models.py`
  (plus `schemas.py` where needed). All routers are aggregated in `app/api/v1/router.py` under `/api/v1`.
- Name/location mismatches vs `AGENT.md`: customers **and** vendors are in `partners`;
  storefront/sales is `sales` but served at `/storefront`; shipments are `fulfillment`
  served at `/shipments`.
- **Services/repositories must never commit.** The `get_db` dependency
  (`app/db/unit_of_work.py`) owns the single commit per request and rolls back on error.
- Any new model must be imported in `app/db/base_all.py`, or Alembic autogenerate and the
  test `create_all` will not see it.
- Company scoping: the `X-Company-Id` header is resolved by `current_company_ctx`; enforce
  with `Depends(guard("<permission>"))`. Permission catalog: `app/core/permissions.py`.
  The backend is authoritative — never trust a client-supplied company id.
- Use `app/shared/money.py` (`money`/`qty`/`dec`), never floats. Document numbers via
  `allocate_number` (`app/shared/numbering.py`). Idempotency via `run_idempotent`
  (`app/shared/idempotency.py`), keyed by `scope` + `Idempotency-Key`.
- Raise `AppError` subclasses (`app/core/exceptions.py`), not `HTTPException`; responses use
  the envelope `{"error": {"code", "message", "details"}}`.
- Health checks: `/health`, `/health/db`.

### Payment gateways (configurable, per company)

- **Config lives in** `payment_gateway_configs` (`PaymentGatewayConfig` in
  `modules/payments/models.py`): one row per `(company_id, provider)` for
  `razorpay` | `stripe` | `mock`, with separate **test** and **live** key sets
  (public key plaintext; secret + webhook secret Fernet-encrypted), an active
  `mode` (`test`|`live`), `supported_methods` (`card`/`upi`) and `priority`
  (lowest wins; mock defaults to 100 so real gateways win ties). Admin API:
  `/api/v1/payments/gateways[...]` (`modules/payments/gateway_router.py`,
  guarded by `payments.manage`); UI: Settings → **Payment gateways** tab.
  Secrets are write-only: responses only expose `has_*` flags + last-4 hints;
  omitting/emptying a secret keeps the stored value, an explicit `null` clears it.
- **Resolution** happens per request in `modules/payments/gateways.py`
  (`resolve_gateway` by storefront method, `get_gateway_by_name` for
  webhooks/refunds). No config + `APP_ENV != prod` falls back to the offline
  `mock` gateway; in prod a missing gateway raises `NO_PAYMENT_GATEWAY`.
  Refunds always use the **mode stored on the original `PaymentRecord.mode`**.
- **Env vars**: `PAYMENT_ENCRYPTION_KEY` (Fernet key for secrets at rest; dev
  derives a warned fallback from `SECRET_KEY`, prod refuses to boot without it)
  and `PUBLIC_API_BASE_URL` (public API origin used to build webhook URLs).
- **Webhook URL format** (paste into the Razorpay/Stripe dashboard):
  `{PUBLIC_API_BASE_URL}/api/v1/payments/webhooks/{provider}/{company_id}` —
  public, no auth; the provider's HMAC signature over the raw body is the only
  gate (`modules/payments/webhooks.py`), applied idempotently by event id.
  Checkout is redirect/SDK style: `guest_checkout`/`guest_pay_order` create a
  provider intent + pending `PaymentRecord` and return `payment.client_payload`;
  the browser confirms via `POST /storefront/shop/orders/{id}/payment/confirm`,
  and both paths finalize through the same `pay:{order_id}` idempotency key.
- **Adding a third provider**: implement `PaymentProviderAdapter` in
  `modules/payments/adapters.py` (`create_intent`, `verify_client_payment`,
  `parse_webhook`, `refund`, `test_connection`), register the instance in
  `ADAPTERS`, add its name to `GATEWAY_PROVIDERS` (and, if keys are prefixed,
  to `_KEY_RULES`), then extend the `_DISPLAY_NAMES`/default-methods maps in
  `gateway_router.py` and the provider list in
  `apps/web/src/features/settings/schemas.ts`.

## Frontend architecture

- Routing is **file-based** (`@tanstack/router-plugin`) under `src/routes/`; `routeTree.gen.ts` is
  generated by `vite build`/`dev` and must not be edited by hand. Structure:
  - `__root.tsx` — mounts `AuthProvider`, renders `<Outlet/>`.
  - `_guest.tsx` — pathless layout for unauthenticated screens (redirects authed users home); child `_guest/login.tsx` → URL `/login`.
  - `_protected.tsx` — pathless layout for the app shell; `beforeLoad` restores the session and
    redirects to `/login` when absent; renders the permission-filtered sidebar/topbar/company switcher.
  - All app screens live in `src/routes/_protected/*.tsx` (URLs unchanged: `/`, `/products`, …).
- Module code lives in `src/features/<module>/` (`schemas.ts` zod, `api.ts`, `queries.ts` `queryOptions`, `<Name>Page.tsx`).
- **Auth**: `src/auth/auth-context.tsx` — `AuthProvider` + `useAuth()` (`isAuthenticated`, `permissions`,
  `roles`, `isAdmin`/`isDeveloper`, `hasPermission`/`hasRole`, `login`/`logout`/`switchCompany`) and the
  non-React `ensureSession()` used by route `beforeLoad`. `src/auth/guards.tsx` has `RequireAuth`,
  `RequirePermission`, `RequireRole`, `RequireAdmin`. `src/hooks/use-permissions.ts` delegates to `useAuth`.
- `src/lib/api-client.ts` — Axios (`axiosClient`/`api`), `baseURL: "/api/v1"`, bearer token +
  `X-Company-Id`, refresh-on-401; rejects with `ApiError` from `src/lib/error-handling.ts`.
- **Every select is a `SheetSelect`** (searchable slide-over from `src/components/sheet.tsx`); never use a native `<select>`.
- `src/lib/query-client.ts` — shared TanStack Query defaults; call `clearSensitiveCaches()` on logout/tenant switch.
- `src/auth/session-store.ts` — `useSyncExternalStore` session; company switch triggers a full
  `window.location.reload()` to avoid stale cross-company cache.
- Requests are relative; `VITE_API_URL` in `docker-compose.yml` is **not** read by the code
  (dev traffic goes through the Vite proxy).

