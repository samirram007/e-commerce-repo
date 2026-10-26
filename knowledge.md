# Knowledge Base

## Project Overview
Full-stack ERP for e-commerce, inventory, delivery and accounting, plus a **public customer storefront** (`/shop/*`) that guests can browse and check out from.
- **Backend**: FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic, Python 3.15, managed by `uv`.
- **Frontend**: React 19 + strict TypeScript + Vite 8, TanStack Router (file-based) & Query, Axios, Tailwind 4, zod.

## Key Code Locations
| Area | Path |
|---|---|
| Backend app | `backend/app/` |
| API aggregation | `backend/app/api/v1/router.py` (mounted at `/api/v1`) |
| Modules | `backend/app/modules/<name>/` – `router.py`, `service.py`, `models.py` (+ `schemas.py` as needed) |
| Base classes / mixins | `backend/app/db/base.py` (`CreatedByMixin` with `blamable`); all models registered in `backend/app/db/base_all.py` |
| Migrations | `backend/migrations/` (Alembic; two revisions: initial schema + `blamable` columns) |
| Shared utilities | `app/shared/money.py` (`money`/`qty`/`dec`), `numbering.py` (`allocate_number`), `idempotency.py` (`run_idempotent`), `pagination.py` (`ListParams`/`apply_list`/`paginate`) |
| Errors / permissions | `app/core/exceptions.py` (`AppError` subclasses), `app/core/permissions.py` (catalog) |
| Public storefront API | `backend/app/modules/storefront/` – served at `/api/v1/storefront/shop/...`; guest identity = optional bearer user, `X-Anon-Id` and `X-Cart-Token` headers. `GET /products/{id}/image` is public (no headers) and serves a generated SVG tile; `GET /pincode/{pin}` validates Indian PIN codes (6 digits, non-zero first digit), resolves delivery rules (exact PIN first, else longest 2–5 digit prefix) and returns state/city/ETA/COD; `GET /cart` items carry server-priced `unit_price`/`tax_amount`/`line_total`. Payments: Razorpay Checkout (`POST /orders/{id}/razorpay` → `…/razorpay/verify`, webhook at `/payments/razorpay/webhook`), plus `POST /orders/{id}/cancel` (refund when paid) and `GET/POST /orders/{id}/returns`. Tax is shown as a GST breakup: `quote_cart(...)` and `GET /invoices/{id}` return `tax_breakup` (`[{rate, amount}]`, one row per GST rate, summing to `tax_total`), which the UI labels `GST 18% · CGST 9% + SGST 9%` |
| Payroll | `app/modules/payroll/` – one balanced GL entry per posted run (`6100` debit, `2400`/`2410` credit) |
| Frontend routes | `frontend/src/routes/` – `_guest` (login), `_protected` (app shell), `shop` (public storefront), `$` catch-all |
| Frontend features | `frontend/src/features/<module>/` (`schemas.ts`, `api.ts`, `queries.ts`, `*Page.tsx`); storefront in `features/storefront/` |
| Auth | `src/auth/auth-context.tsx` (`AuthProvider`, `useAuth`, non-React `ensureSession` for `beforeLoad`), `src/auth/guards.tsx`, `src/auth/session-store.ts` |
| Transport / cache | `src/lib/api-client.ts` (Axios, `/api/v1`, bearer + `X-Company-Id`), `src/lib/error-handling.ts` (`ApiError`), `src/lib/query-client.ts` |
| Tables & forms | `src/hooks/use-list-state.ts`, `src/components/data-table.tsx` (`ServerDataTable`), `src/components/crud-form.tsx`; every select is `SheetSelect` (`src/components/sheet.tsx`) |
| Tests | `backend/tests/` (110 tests, SQLite); `frontend/src/**/*.test.ts` (vitest, config `frontend/vitest.config.ts`) |

## Commands
**Backend (from `backend/`):**
- `uv sync` – install deps (`.venv/` present)
- `uv run pytest` – all tests on a throwaway **SQLite** DB (no Postgres/Redis needed)
- `uv run pytest tests/test_accounting_invariants.py::test_unbalanced_journal_rejected` – single test
- `uv run alembic upgrade head` – migrate (`DATABASE_URL`, `ALEMBIC_DATABASE_URL` overrides)
- `uv run alembic revision --autogenerate -m "..."` – new revision
- `uv run uvicorn app.main:app --reload` – dev server `:8000`
- `uv run python -m app.seed` – idempotent seed (admin, demo company/COA/warehouse, employees, draft payroll)

**Frontend (from `frontend/`) — pnpm only** (npm/yarn blocked by `scripts/ensure-pnpm.mjs`; `packageManager` pins pnpm):
- `corepack enable` once, then `pnpm install`
- `pnpm dev` – Vite `:5173`, proxies `/api` → `VITE_API_PROXY ?? http://localhost:8000`
- `pnpm build` – `vite build && tsc -b` (vite regenerates `routeTree.gen.ts`, then typechecks)
- `pnpm test` – `vitest run`

No backend lint/format/typecheck tool is configured (`.ruff_cache`/`.mypy_cache` are only mentioned in `.gitignore`).

## Routing & Auth Flow (frontend)
- `__root.tsx` mounts `AuthProvider` + `ThemeProvider`; `<Outlet/>` renders the match.
- `_guest.tsx` – unauthenticated screens; `beforeLoad` calls `ensureSession()` and redirects an already-signed-in visitor to `/`. Child `_guest/login.tsx` → URL `/login` and validates `?redirect=` (internal path only).
- `_protected.tsx` – app shell (permission-filtered sidebar/topbar, company + fiscal-year pickers); `beforeLoad` restores the session or redirects to `/login`.
- `shop.tsx` – public storefront shell (`StoreProvider` + `ShopLayout`); no auth required. Routes: `/shop/` (home = hero, category grid, then `ProductRail` panels: trending, new arrivals, budget picks, top departments), `/shop/products/` (filters via `?category=&q=&sort=`), `/shop/products/$productId`, `/shop/cart`, `/shop/checkout`, `/shop/interests`, `/shop/orders`.
- `$.tsx` – unmatched URLs: guests go to `/shop`, signed-in users to `/` (never straight to the login screen).
- Storefront guest identity lives in `features/storefront/store.ts` (localStorage `shop.cartToken`, `shop.anonId`, `shop.companyId`); `api.ts` attaches them plus the bearer token when signed in.
- After sign-in, `LoginPage` navigates to `?redirect=` when it is a safe internal path, otherwise `/`.
- `routeTree.gen.ts` is generated — never edit by hand.

## Conventions & Gotchas
- **Never use floats for money** — `app/shared/money.py`; monetary columns are `NUMERIC`.
- **Services/repositories never commit**; `get_db` (`app/db/unit_of_work.py`) owns the single commit per request and rolls back on error.
- **Company scoping**: `X-Company-Id` is resolved by `current_company_ctx`; enforce with `Depends(guard("<permission>"))`. Backend is authoritative.
- **New models** must be imported in `app/db/base_all.py` or neither Alembic autogenerate nor the test `create_all` sees them.
- Raise `AppError` subclasses (not `HTTPException`); error envelope `{"error": {"code", "message", "details"}}`.
- **Server-side list contract**: backend `app/shared/pagination.py`; frontend drives it with `useListState()` + `ServerDataTable`, includes `listQueryKey(list)` in query keys, invalidates the feature root after mutations.
- **Name/location mismatches**: customers & vendors live in `modules/partners`; storefront/sales is `modules/sales` (served at `/storefront` for the ERP API); shipments are `modules/fulfillment` at `/shipments`.
- **Payroll rules**: one run per company/period (cancelled frees it); posted runs cannot be cancelled (reverse the journal); totals recomputed at post time.
- **Blamable audit**: `CreatedByMixin.blamable` (bool, default false) marks creates/modifications as intentionally attributed to the acting user.
- **Postgres vs SQLite**: SQLite tests do not enforce `VARCHAR` length or other dialect constraints — Postgres-only bugs will not show up in `uv run pytest`.
- **Payments**: Razorpay keys (`RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`/`RAZORPAY_WEBHOOK_SECRET`) switch the storefront from the sandbox gateway to hosted Checkout. Order creation stores a *pending* `PaymentRecord` keyed `order:<rzp_order_id>`; signature verification promotes that row to the captured payment (idempotent — callback + webhook can both arrive). Refunds go through `payments.provider_refund` → `RazorpayAdapter`.
- **Cash on delivery**: a COD checkout calls `sales.accept_cash_on_delivery` — the order goes to `confirmed` (fulfillable) with an open `PaymentRecord` (`provider=cash`, `method=cod`, `provider_ref=<cod:order_id>`, `status=pending`) and no invoice. `fulfillment.transition_shipment(… "delivered")` calls `sales.collect_cash_on_delivery`, which settles that receipt, marks the order paid and issues/posts the invoice; cancelling before delivery voids the pending receipt. COD refunds (cancellations after payment, returns) go through `CashAdapter`.
- **Seeding targets the demo company**: `python -m app.seed` looks for a company named `Demo Retail Co` (falling back to the admin's first company) so leftover test companies are not topped up. `store_info` resolves duplicate storefront slugs by oldest company. Demo pricing uses Indian GST slabs — `_seed_taxes` upserts `GST5`/`GST12`/`GST18` with 18% as the only default (sales and purchase) and retires the old `VAT10` "Sales VAT 10%" rate.
- **Abandoned gateway checkouts**: `sales.expire_unpaid_orders` cancels `pending_payment` orders older than `ORDER_PAYMENT_TIMEOUT_MINUTES` (default 30), releasing reservations and voiding their open gateway intents; `confirmed` COD orders and paid orders are untouched. It runs before `GET /storefront/shop/orders` and from a background task in `app.main.lifespan` every `ORDER_EXPIRY_SWEEP_SECONDS` (default 300, 0 disables). A late Razorpay capture on a cancelled order is refunded automatically (`storefront._late_capture_refund`): the webhook's `payment.captured`/`order.paid` and the browser `…/razorpay/verify` callback both book the receipt and a `payment`-direction refund keyed `Refund of <payment_id>`, so a duplicate delivery never refunds twice. Orders carry `cancel_reason` (`cancelled_by_customer | cancelled_by_staff | payment_timeout`, migration `73ca42fd5168`) which the storefront renders on the orders page.
- **Printable GST invoice**: `InvoiceOut` adds `customer_address`, `customer_tax_identifier` and `tax_breakup[].taxable`; the ERP's `InvoicePrint` component (opened from the invoice sheet) renders seller GSTIN/address (from `GET /companies/{id}`), the buyer's address/GSTIN, taxable value and a CGST/SGST split per slab (`lib/format.splitTaxAmount` keeps the paise exact), then prints via `@media print` rules for `.invoice-print`. The buyer address is the invoice's `customer_address` snapshot: order-sourced invoices copy `order.billing_address or order.shipping_address`, manual invoices accept a `customer_address` on create. Demo seed sets the company's address/GSTIN and seeds a GST-registered customer `C-010` with a delivered demo order.
- **HSN/SAC on invoices**: `products.hsn_sac` (validated 4–8 digits as `BAD_HSN_SAC`, editable in the product form) is snapshotted to `invoice_lines.hsn_sac_snapshot` when the invoice is created and returned as `InvoiceLineOut.hsn_sac`; `InvoicePrint` renders it as the HSN/SAC column. Migration `b7f3a91c4e20`. Demo products get a code per leaf category from `seed._HSN_BY_CATEGORY` (also backfilled onto products seeded earlier).

- **HSN/SAC backfill**: a one-off `python -m app.backfill_hsn` (or `uv run python - <<'PY' ...`) iterates all posted invoices and sets `InvoiceLine.hsn_sac_snapshot` from the linked product's `hsn_sac` where the snapshot is currently null. Already run on the demo database: 34 of 38 posted invoices received a code; lines without a product link or a product without an HSN code are left as `null` (printed as `—` on the invoice).
- **GST ledger split**: the default chart now has output `2110 CGST Payable` / `2120 SGST Payable` (roles `cgst_payable`/`sgst_payable`) and input credit `1160 Input CGST` / `1170 Input SGST` (roles `input_cgst`/`input_sgst`, both assets). Invoice posting credits the payable pair and credit notes debit it; vendor bills (from-receipt and ad-hoc) debit the input pair via `purchasing._input_tax_lines`. In every pair the SGST leg takes the rounding remainder so the entry balances, and `taxes.cgst_share` rounds CGST per GST slab so the ledger matches the printed invoice. `accounting.gst_payable_codes` / `gst_input_codes` fall back to the single `2100 Sales Tax Payable` for charts that predate the split.

- **GST summary report**: `GET /api/v1/accounting/reports/gst-summary?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD` returns per-date totals of output CGST/SGST (2110/2120 credits) and input CGST/SGST (1160/1170 debits), with net per component (`net = output - input`). A positive net means GST payable; a negative net means input credit exceeds output. The response includes per-date rows and a grand total across the period.
- **Local DB**: this machine uses the `postgresql-x64-18` Windows service (not docker-compose); percent-encode URL-reserved chars in the password (`@` → `%40`), and `migrations/env.py` escapes `%` for Alembic's ConfigParser. With no `DATABASE_URL` the default is `sqlite:///./erp_dev.db`. `psycopg[binary]` is a dependency on all platforms.
- **Frontend**: strict TS; components never call Axios directly (use `api.ts` + `queries.ts` query options); clear sensitive caches on logout/company switch; company switch triggers a full `window.location.reload()`, so don't add reload effects that run on mount.
- **Docker**: `docker-compose.yml` declares postgres 16, redis 7, `api`, `web`, but neither service has a `Dockerfile`, so `docker compose build` cannot succeed as-is. `VITE_API_URL` in compose is not read by the code (dev uses the Vite proxy).

## Docs
- `AGENT.md` — authoritative product/architecture spec (business rules, invariants, module expectations).
- `AGENTS.md` — short operational notes for agents.
