# Knowledge Base

## Project Overview
**Freebuff** – a full-stack ERP platform for e-commerce, inventory, delivery and accounting.
- **Backend**: FastAPI + SQLAlchemy 2.x + Alembic, Python 3.12, managed by `uv`.
- **Frontend**: React 18 + strict TypeScript + Vite, TanStack Router/Query, Axios.

## Key Code Locations
| Area | Path |
|---|---|
| Backend app | `backend/app/` |
| API routers | `backend/app/api/v1/router.py` (aggregates all) |
| Modules | `backend/app/modules/<name>/` – each has `router.py`, `service.py`, `models.py` (and `schemas.py` as needed) |
| Services & repositories | `backend/app/modules/*/service.py` – **never commit**; the `get_db` dependency owns the single commit per request |
| Models | `backend/app/db/models.py` + `backend/app/db/base_all.py` (new models must be imported here) |
| DB / Migrations | `backend/migrations/` (Alembic); one initial revision exists |
| Shared utilities | `backend/app/shared/money.py` (`money`/`qty`/`dec`), `backend/app/shared/numbering.py` (`allocate_number`), `backend/app/shared/idempotency.py` (`run_idempotent`) |
| Exceptions | `backend/app/core/exceptions.py` – use `AppError` subclasses, not `HTTPException` |
| Permissions | `backend/app/core/permissions.py` – catalog of permissions; enforce via `Depends(guard("<permission>"))` |
| Companies / vendors | Customers **and** vendors live in `partners`; storefront/sales is `sales` served at `/storefront`; shipments are `fulfillment` served at `/shipments` |
| Frontend | `frontend/src/` – file-based routes in `src/routes/` (`_guest`/`_protected` layouts); feature modules in `src/features/<module>/`; auth in `src/auth/auth-context.tsx`; API client `src/lib/api-client.ts` (+ `src/lib/error-handling.ts`); query client `src/lib/query-client.ts` |
| Tests | `backend/tests/` – 30 tests; SQLite via `conftest.py`; single Alembic revision test |

## Commands
**Backend (run from `backend/`):**
- `uv sync` – install dependencies
- `uv run pytest` – run all tests (throwaway SQLite DB)
- `uv run alembic upgrade head` – run migrations (reads `DATABASE_URL`)
- `uv run uvicorn app.main:app --reload` – dev server at `:8000`
- `uv run python -m app.seed` – idempotent seed (admin + demo company/chart/warehouse)

**Frontend (run from `frontend/`) — pnpm only:**
- `corepack enable` then `pnpm install` – install dependencies (npm/yarn are blocked by `scripts/ensure-pnpm.mjs`)
- `pnpm dev` – Vite at `:5173`, proxies `/api` → `http://localhost:8000`
- `pnpm build` – `vite build && tsc -b` (vite regenerates `routeTree.gen.ts`)
- `pnpm test` – `vitest run` (no test files yet)

## Notable Conventions & Gotchas
- **No floats**: always use `app/shared/money.py` (`money`/`qty`/`dec`).
- **Idempotency**: `run_idempotent` keyed by `scope` + `Idempotency-Key`.
- **Number allocation**: use `allocate_number` from `app/shared/numbering.py`.
- **Company scoping**: the `X-Company-Id` header is resolved by `current_company_ctx`; enforce with `Depends(guard("<permission>"))`. The backend is authoritative — never trust client-supplied company id.
- **Services/repositories must never commit**; `get_db` (`app/db/unit_of_work.py`) owns the single commit per request and rolls back on error.
- **New models** must be imported in `app/db/base_all.py`, or Alembic autogenerate and the test `create_all` will not see it.
- **Permissions catalog**: `app/core/permissions.py`. Use `Depends(guard("<permission>"))`.
- **Route naming mismatches vs AGENT.md**: customers & vendors → `partners`; storefront/sales → `sales` at `/storefront`; shipments → `fulfillment` at `/shipments`.
- **Frontend uses pnpm only** (npm/yarn blocked by `frontend/scripts/ensure-pnpm.mjs`; `packageManager` pins pnpm). It typechecks and builds: `pnpm build` exits 0. Routes are file-based under `src/routes/`; every select uses `SheetSelect`.
- **Windows dev**: `psycopg` excluded on Windows, so default `sqlite:///./erp_dev.db` is used.
- **Alembic**: only one revision exists (`migrations/versions/5d98e9df63ca_initial_schema.py`); any new model requires import in `base_all.py` + new revision.
- **Env vars**: `DATABASE_URL` for Alembic; `ALEMBIC_DATABASE_URL` to override. `.env.example` present.
- **Docker**: `docker-compose.yml` brings up postgres 16, redis 7, `api`, `web`. The `web` service uses pnpm (`corepack enable && pnpm install --frozen-lockfile && pnpm run dev`). Note neither service has a `Dockerfile` yet, so `build:` fails as-is.

## Quick Reference: Money & Numbers
```python
from app.shared.money import money, qty, dec
# Never use float for monetary values.
```

## Blamable (auto-audit)
- **`blamable`** column added to `CreatedByMixin` in `backend/app/db/base.py` (line ~53).
- A `Boolean` field defaulting to `False`; set to `True` to auto‑track that an acting user was responsible for the creation/modification event.
- When `blamable=True` the `created_by` field is populated automatically by the service layer (e.g. `created_by=actor_user_id`) and the ORM records both the user ID and that the action was intentional/blamable.
- Use it in any model that inherits `CreatedByMixin` — no extra code required beyond setting the flag.
- Example:
  ```python
  from sqlalchemy.orm import Mapped
  class MyModel(CreatedByMixin):
      blamable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  ```
- To enable globally, ensure the service always passes `actor_user_id` when creating/updating records with `blamable=True`.
```