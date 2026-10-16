# AGENT.md — E-commerce, Inventory, Delivery, and Accounting ERP

## 1. Project Description

Build a production-oriented, modular e-commerce and business management platform with a complete frontend and backend. The system must support online product sales, purchasing, inventory and storage locations, vendor management, delivery and fulfillment, invoicing, and double-entry accounting.

The platform must be designed for correctness, traceability, maintainability, and future growth. Treat accounting and inventory as auditable business domains—not merely CRUD screens. All posted financial and stock movements must be traceable to their source documents and must follow consistent transaction rules.

This file is the project-level source of truth for AI coding agents. Before implementing a feature, inspect the existing codebase and follow established conventions. Do not replace working architecture or introduce duplicate abstractions without a clear reason.

## 2. Technology Stack

### Backend

- Python with FastAPI.
- Pydantic v2 for request, DTO, settings, and response validation.
- SQLAlchemy 2.x ORM.
- Alembic for database migrations.
- PostgreSQL recommended for production. Keep database-specific SQL isolated if MySQL/MariaDB support is required.
- Uvicorn as the ASGI server.
- Redis for optional shared cache, distributed coordination, and background-job support where justified.
- Pytest and HTTPX for testing.
- Structured logging and centralized exception handling.
- OpenAPI as the API contract.

### Frontend

- React and TypeScript in strict mode.
- TanStack Router for routing and route-level data/loading patterns.
- TanStack Query for server state, caching, invalidation, retries, and mutations.
- Axios for HTTP requests, credentials, interceptors, and normalized transport errors.
- Zod for frontend form and client-side validation.
- React Hook Form for form state and validation integration.
- TanStack Table for data-heavy tables.
- TanStack Virtual where large lists require virtualization.
- TanStack Form may be used where it offers a clear benefit; do not use multiple form-state libraries for the same form.
- A consistent component system and accessible UI primitives (for example, shadcn/ui with a supported primitive library).
- Vitest and React Testing Library for frontend tests; Playwright for end-to-end tests.

### Contract and type generation

- FastAPI OpenAPI schemas are the canonical API contract.
- Generate TypeScript types/client definitions from OpenAPI when practical; do not manually duplicate large API contracts.
- Zod remains useful for client-side form feedback, but server-side Pydantic validation is authoritative.
- Keep generated files clearly marked and do not hand-edit generated output.
- Document any intentional frontend/backend validation differences.

## 3. Architecture Principles

Use a **modular monolith first**: one deployable backend with strong business-module boundaries. Do not split into microservices unless a concrete scaling, reliability, ownership, or deployment requirement justifies it.

### Backend request flow

`Router → Request Schema → Application/Service Layer → Repository/Unit of Work → SQLAlchemy Models → Database`

Responses flow through explicit response schemas and, where necessary, resource mappers.

- **Router:** HTTP concerns only—routing, authentication dependencies, request/response schemas, status codes.
- **Request schemas:** validate external input using Pydantic.
- **DTOs:** represent use-case input/output when distinct from HTTP schemas or ORM models.
- **Services:** implement business rules and orchestrate use cases and modules.
- **Repositories:** encapsulate queries and persistence operations.
- **Models:** represent database entities and ORM relationships; avoid embedding multi-module workflows in model methods.
- **Response schemas/resources:** define exactly what API clients receive; never expose ORM fields indiscriminately.
- **Unit of Work / transaction boundary:** coordinate commits and rollbacks for a complete business operation.
- **Dependencies/composition:** construct sessions, repositories, services, and authorization context through explicit dependency providers.
- **Events/background tasks:** use for non-critical follow-up work. Do not use an untracked background task for a critical financial posting.

### Frontend request flow

`Route/Page → Feature Component/Form → TanStack Query Hook → Frontend API Service → Axios Client → FastAPI`

- Components should not call Axios directly.
- Frontend API services should contain transport calls and response typing, not accounting or inventory business rules.
- TanStack Query owns server-state caching and synchronization.
- Local component state owns transient UI state.
- Zod and React Hook Form validate user input and provide accessible error feedback.
- Do not treat client validation as a security boundary.

## 4. Suggested Repository Structure

Adapt this structure to the existing repository if it already has a sound equivalent. Avoid creating empty folders or placeholder abstractions that are not used.

```text
project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/router.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   ├── exceptions.py
│   │   │   └── permissions.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── unit_of_work.py
│   │   ├── shared/
│   │   │   ├── pagination.py
│   │   │   ├── cache.py
│   │   │   ├── idempotency.py
│   │   │   └── money.py
│   │   ├── modules/
│   │   │   ├── identity/
│   │   │   ├── companies/
│   │   │   ├── fiscal_years/
│   │   │   ├── customers/
│   │   │   ├── vendors/
│   │   │   ├── catalog/
│   │   │   ├── pricing/
│   │   │   ├── sales/
│   │   │   ├── purchasing/
│   │   │   ├── inventory/
│   │   │   ├── storage/
│   │   │   ├── fulfillment/
│   │   │   ├── delivery/
│   │   │   ├── invoicing/
│   │   │   ├── payments/
│   │   │   ├── accounting/
│   │   │   ├── taxes/
│   │   │   ├── returns/
│   │   │   ├── reports/
│   │   │   └── audit/
│   │   └── workers/
│   ├── migrations/
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── routes/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── catalog/
│   │   │   ├── sales/
│   │   │   ├── purchasing/
│   │   │   ├── inventory/
│   │   │   ├── storage/
│   │   │   ├── delivery/
│   │   │   ├── invoicing/
│   │   │   ├── accounting/
│   │   │   └── reports/
│   │   ├── services/
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── query-client.ts
│   │   │   └── generated/
│   │   ├── schemas/
│   │   ├── types/
│   │   ├── hooks/
│   │   └── utils/
│   ├── tests/
│   └── package.json
├── docs/
├── deployment/
├── .gitignore
└── README.md
```

A typical backend module may contain:

```text
modules/inventory/
├── router.py
├── models.py
├── schemas/
│   ├── requests.py
│   ├── responses.py
│   └── filters.py
├── dto/
├── repository.py
├── interfaces.py
├── service.py
├── mapper.py
├── dependencies.py
├── exceptions.py
└── tests/
```

Use a single `schemas.py` or fewer files for small modules. Split files when the module complexity justifies it.

## 5. Business Scope and Modules

### 5.1 Identity, access, and company context

- Users, roles, permissions, sessions, and audit history.
- Enforce authorization on the backend for every protected operation.
- Support a user who can access one or more companies, subject to explicit grants.
- Every company-owned business record must be scoped by `company_id` where appropriate.
- Resolve the active company and fiscal year from a validated, authorized context; never trust a client-supplied identifier without checking access.
- Record who created, modified, approved, posted, cancelled, or reversed a business document.

### 5.2 Companies and fiscal years

- Company profile, addresses, contact details, currency, locale, timezone, tax identifiers, and accounting settings.
- Fiscal-year start/end dates, status, opening/closing workflow, and permitted posting dates.
- Validate that posted transactions belong to an open fiscal year and valid accounting period.
- Support opening balances and controlled year-end carry-forward for ledgers and stock.
- Do not mix prior-year operational movements into current-year reports without an explicit opening-balance/carry-forward rule.
- Preserve historical document references and accounting auditability after a year is closed.

### 5.3 Product catalog and pricing

- Products, SKUs, categories, brands, descriptions, images, units of measure, variants, barcodes, and status.
- Purchase cost, selling price, price lists, discounts, and effective date ranges.
- Define whether a product is stock-tracked, service-only, or non-inventory.
- Support unit conversions only through explicit, validated conversion rules.
- Never use floating-point arithmetic for money.

### 5.4 Customers and vendors

- Contact and address management, tax details, payment terms, credit limits, opening balances, and status.
- Vendor purchase history, payable balances, purchase returns, and payments.
- Customer sales history, receivables, sales returns, refunds, and receipts.
- Validate duplicate business identifiers according to company-level rules.
- Maintain audit history for important master-data changes.

### 5.5 Sales and e-commerce

- Product browsing/search, category and product details, price display, cart, checkout, customer addresses, and order history.
- Orders, order lines, discounts, shipping charges, taxes, status transitions, and payment state.
- Stock availability and reservation checks during checkout.
- Idempotent checkout/payment operations to prevent duplicate orders or charges.
- Separate order creation, payment confirmation, fulfillment, invoice issuance, and delivery status.
- Support guest checkout only if explicitly enabled; protect customer data and prevent insecure object access.
- Define cancellation and refund rules for each order state.

### 5.6 Purchasing and vendors

- Purchase orders, approval, goods receipt, vendor bills, vendor credit notes, and vendor payments.
- Partial receipts, backorders, price differences, purchase returns, and cancelled documents.
- Record the received quantity separately from the ordered quantity.
- Use stock movement records to track actual receipt and return quantities.
- Reconcile vendor bills against purchase orders and goods receipts when required.

### 5.7 Inventory

- Stock ledger/movement history, stock on hand, reserved quantity, available quantity, and valuation.
- Receipts, issues, transfers, adjustments, returns, opening stock, and physical stock counts.
- Support configurable costing methods such as weighted average or FIFO only when fully implemented and tested.
- Track stock by company, product, storage location, and batch/serial number when applicable.
- Maintain immutable posted movement history; correct errors through reversal/adjustment entries rather than silently editing posted movements.
- Define negative-stock policy explicitly; default to preventing negative stock unless a company setting and business rule permit it.
- Use concurrency controls and database constraints to avoid overselling or double allocation.

### 5.8 Storage locations and warehouses

- Warehouse/site, zone, aisle, rack, shelf, bin, and other configurable location hierarchy.
- Validate that a storage location belongs to the correct company/warehouse.
- Support transfers between locations and warehouses with clear source and destination movements.
- Support batch, lot, expiry, and serial tracking where product configuration requires it.
- Distinguish physical on-hand stock, reserved stock, damaged stock, and stock in transit.

### 5.9 Fulfillment and delivery

- Pick lists, packing, shipment, delivery assignment, dispatch, tracking events, proof of delivery, failed delivery, and return-to-origin.
- Carrier/provider integration behind adapters so the core domain does not depend on one vendor.
- Delivery fee, shipment status, delivery address snapshot, tracking number, and delivery history.
- Enforce valid status transitions.
- Avoid marking an order delivered solely because a carrier API request was sent.
- Handle webhook retries idempotently and verify webhook authenticity.

### 5.10 Invoicing and payments

- Sales invoices, credit notes, debit notes where applicable, payment receipts, vendor bills, and payment vouchers.
- Sequential document numbering scoped by company and document type, with safe concurrency handling and configurable fiscal-year rules.
- Document dates, due dates, currency, exchange-rate policy if multi-currency is enabled, line-level taxes, discounts, rounding, and totals.
- Partial payments, multiple payment allocations, overpayments, refunds, and outstanding balances.
- Store a snapshot of legally or commercially relevant customer, address, tax, item description, and price data on issued documents.
- Posted invoices must not be silently rewritten. Use credit notes, cancellation, or reversal workflows according to document status and applicable law.

### 5.11 Accounting

Implement a genuine double-entry general ledger.

- Chart of accounts and account groups.
- Ledger accounts and opening balances.
- Journal entries and journal lines.
- Sales, purchase, receipt, payment, tax, inventory, cost-of-goods-sold, returns, and adjustment postings.
- Accounts receivable and accounts payable subledgers.
- Cash/bank accounts, payment allocations, and bank reconciliation foundation.
- Trial balance, general ledger, profit and loss, balance sheet, cash/bank book, daybook, receivable/payable aging, and tax reports as required.
- Every posted journal entry must balance: total debits equal total credits within the company's currency precision and rounding rules.
- Prevent posting into closed fiscal years or closed periods.
- Link each journal entry to its source document using stable source type/ID or a well-defined relation.
- Use reversal entries for corrections; retain the original posted entry and full audit trail.
- Keep accounting posting rules centralized and testable. Do not create journal entries ad hoc from route handlers.

Accounting rules must be reviewed for the target jurisdiction and tax regime before production use. Do not claim legal or tax compliance merely because calculations exist.

### 5.12 Returns, refunds, and adjustments

- Sales returns, purchase returns, refund requests, refund payments, stock disposition, credit notes, and linked accounting reversals.
- Validate quantities against the original transaction and prior returns.
- Track whether returned goods are resalable, damaged, quarantined, or discarded.
- Prevent duplicate refund execution using idempotency keys and provider transaction references.

### 5.13 Reporting and audit

- Filterable and paginated operational reports.
- Sales, purchases, stock ledger, stock valuation, stock aging where supported, delivery performance, invoices, payment status, customer balances, vendor balances, and accounting reports.
- Date ranges must use company timezone and clearly defined inclusive/exclusive boundaries.
- Enforce company and permission scopes in every report.
- Export CSV/XLSX/PDF only with appropriate permissions and safe handling of large datasets.
- Audit significant changes and posting actions with actor, timestamp, action, entity, and relevant before/after data while avoiding secrets and unnecessary sensitive information.

## 6. Database and Data Integrity Rules

- Use SQLAlchemy 2.x typed mappings and Alembic migrations.
- Add foreign keys, unique constraints, check constraints, and indexes deliberately.
- Include `company_id` on company-owned entities and enforce company consistency in service logic and, where practical, database constraints.
- Use explicit primary keys and stable document identifiers.
- Use `Decimal` / SQL `NUMERIC` for monetary values; never `float` for money.
- Store timestamps in UTC; apply company timezone when presenting or interpreting business dates.
- Define deletion policies. Prefer soft deletion for eligible master data; do not delete posted financial/stock history.
- Use optimistic locking or suitable row locks for stock allocation, document numbering, and other contention-sensitive workflows.
- Make multi-step business operations atomic where they share a database transaction.
- Avoid implicit commits inside repositories or nested services. The use-case transaction boundary owns commit/rollback.
- Keep ORM relationships useful for navigation but avoid unbounded eager loading and N+1 query patterns.
- Avoid circular imports by centralizing model registration and using string-based relationship targets where appropriate.

## 7. Cache Architecture — Backend and Frontend

Caching must improve performance without becoming a source of incorrect prices, balances, stock availability, permissions, or accounting results.

### 7.1 Frontend caching

Use TanStack Query as the primary server-state cache.

- Establish a shared `QueryClient` with documented defaults for `staleTime`, `gcTime`, retry policy, and refetch behavior.
- Use stable, typed query keys that include all relevant filters, pagination, company context, and fiscal-year context.
- Invalidate or update related queries after mutations.
- Use optimistic updates only where rollback and conflict handling are safe.
- Cancel or isolate queries when the active company, user, or permissions change.
- Clear sensitive cached data on logout and account/tenant switches.
- Do not persist sensitive financial, personal, or permission-dependent data to browser storage by default.
- Avoid duplicating TanStack Query data into a second global state store without a clear need.
- Configure Axios with an explicit base URL, timeouts, credential policy, and consistent error normalization.
- Do not put secrets in frontend environment variables; browser-exposed variables are public.

### 7.2 Backend caching

- Define a cache abstraction in `shared/cache.py` so application code does not depend directly on Redis calls.
- Use Redis for shared caching when multiple backend workers/instances need a consistent cache.
- In-process memory caches may be used only for non-critical, process-local data with explicit limitations.
- Cache only data with a defined key, ownership scope, freshness policy, invalidation rule, and fallback behavior.
- Include company, fiscal year, language/currency, relevant filters, and permission scope in keys whenever they affect the result.
- Never return a cached result across unauthorized company or user boundaries.
- Use TTLs as a safety net, not as the only invalidation strategy for mutable business data.
- Invalidate or version cache entries after successful transaction commit, not before commit.
- Cache catalog lookups, stable reference data, and expensive reports only after measuring the need.
- Be conservative with stock availability, current prices, balances, authorization, payment state, fiscal-year status, and accounting summaries. Prefer authoritative database reads or carefully designed versioned caches.
- Never cache a failed or partial transaction as if it succeeded.
- Use cache stampede protection or request coalescing for expensive hot keys when justified.
- Make cache failure degrade safely to the database for non-critical caches. Do not silently bypass security or consistency controls when a critical dependency fails.
- Document cache ownership and invalidation for every cached domain.
- Avoid storing raw payment credentials, passwords, access tokens, or other secrets in caches.

### 7.3 File and object-storage caching

Support file handling for product images, invoices, receipts, shipment documents, and exports.

- Store file metadata in the database and file contents in an appropriate object store or managed file storage.
- Use private storage by default for invoices, receipts, customer documents, and exports.
- Use generated object keys rather than trusting client filenames.
- Validate file size, content type, file signature where appropriate, authorization, and allowed extensions.
- Serve private files through authorized endpoints or short-lived signed URLs.
- Support `Cache-Control`, `ETag`, and conditional requests for public/static assets where appropriate.
- Use immutable, versioned URLs for public product media so CDN/browser caching is safe.
- Do not publicly cache private documents or tenant-specific files.
- Keep generated reports and exports access-controlled, expiring, and cleaned up according to retention policy.
- Do not assume a local disk is shared between backend replicas; use object storage or a deliberately shared volume where necessary.
- Include file upload/download tests, authorization tests, and cleanup behavior.

### 7.4 Cache invalidation patterns

For each cached domain, document:

1. Cache key and schema/version.
2. TTL and stale-data tolerance.
3. Read-through or explicit population strategy.
4. Mutation/event that invalidates or increments the version.
5. Behavior on Redis outage.
6. Company/user/permission isolation requirements.
7. Tests for stale and cross-company data.

For transaction-sensitive data, perform invalidation after a successful commit. If invalidation reliability is critical, consider a transactional outbox or version-based invalidation mechanism.

## 8. API Standards

- Prefix APIs with `/api/v1`.
- Use plural resource paths and appropriate HTTP methods/status codes.
- Use Pydantic request and response schemas.
- Keep a consistent error response format, for example:
  `{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed", "details": [] } }`
- If adopting a standard success envelope, apply it consistently and document pagination metadata.
- Implement pagination, search, sorting, filtering, and date filtering through reusable, validated patterns.
- Validate sort fields against an allowlist; never interpolate arbitrary client input into SQL.
- Add idempotency support to payment, checkout, posting, and webhook endpoints where duplicate execution is dangerous.
- Use `201` for successful resource creation where appropriate, `204` for successful no-content operations, and meaningful `4xx`/`5xx` codes.
- Keep OpenAPI tags, summaries, response schemas, and security requirements current.
- Use explicit request timeouts and sensible payload/file limits.
- Configure CORS with explicit trusted origins in production; do not combine wildcard origins with credentialed requests.

## 9. Authentication, Authorization, and Security

- Select and document an authentication strategy before implementation. Use established libraries for password hashing and token/session handling.
- Enforce authorization on every backend request; frontend route guards are only a user-experience aid.
- Apply least-privilege role and permission checks to company, fiscal year, accounting, inventory, payment, export, and administration operations.
- Protect against IDOR by verifying access to every requested resource and related entity.
- Validate company context and relationships across all submitted IDs.
- Store secrets only in environment/secret management systems; commit `.env.example`, never real credentials.
- Set secure cookie flags if cookie-based authentication is used, and configure CSRF protection where applicable.
- Rate-limit login, password reset, checkout, and other abuse-prone endpoints where appropriate.
- Verify payment and carrier webhooks cryptographically and make handlers idempotent.
- Avoid logging passwords, tokens, full payment data, or unnecessary personal information.
- Apply safe file upload handling and access control.
- Use dependency and container scanning as part of the delivery pipeline.

## 10. Frontend Standards

- Use strict TypeScript; avoid `any` unless justified and isolated.
- Organize UI by business feature rather than creating one giant components directory.
- Keep API transport in `services/`; keep query/mutation logic in hooks or feature-level query modules.
- Centralize Axios configuration and error normalization.
- Define query-key factories for each feature.
- Use Zod and React Hook Form for form schemas and accessible validation.
- Prefer server-driven pagination/filtering for large datasets.
- Use TanStack Table for sorting, filtering, column visibility, selection, and table interactions; keep server-side behavior authoritative for large data.
- Use TanStack Virtual only when list size warrants it.
- Use TanStack Router route definitions, loaders, search parameters, and route guards consistently.
- Provide loading, empty, error, success, and permission-denied states.
- Use accessible labels, keyboard navigation, focus management, semantic HTML, and contrast-safe design.
- Confirm destructive actions and clearly distinguish draft, approved, posted, cancelled, and reversed document states.
- Do not calculate authoritative tax, ledger, stock, or invoice totals exclusively in the browser. The backend recalculates and validates all authoritative amounts.
- Avoid storing financial business rules in UI components.

## 11. Testing Requirements

### Backend

- Unit tests for services and domain rules.
- Repository tests against a real test database where practical.
- API tests for request validation, permissions, response schemas, pagination, and error handling.
- Transaction rollback tests for multi-module workflows.
- Accounting invariants: every posted journal balances.
- Inventory invariants: movements reconcile to on-hand quantities and reservations.
- Fiscal-year tests: closed periods reject prohibited postings.
- Idempotency tests for checkout, payment, posting, and webhook handling.
- Concurrency tests for stock allocation and document numbering.
- Cache isolation/invalidation tests, including company and fiscal-year boundaries.
- File access, upload validation, and private-document authorization tests.

### Frontend

- Unit tests for schemas, formatters, query-key factories, and API service error handling.
- Component tests for forms, validation, permissions, loading/error states, and data tables.
- Tests that mutations invalidate or update relevant TanStack Query keys.
- End-to-end tests for a complete flow: catalog → cart → checkout → payment result → fulfillment → invoice.
- End-to-end tests for purchasing → goods receipt → stock ledger → vendor bill → accounting entries.
- Test company/fiscal-year switching and ensure stale cached data is not shown.

### Quality gates

Before marking a task complete:

1. Run formatting, linting, static type checks, and relevant tests.
2. Run migrations against a disposable test database.
3. Verify OpenAPI output and generated frontend types if applicable.
4. Check authorization, transaction boundaries, cache invalidation, and audit effects.
5. Document configuration or migration changes.
6. Do not claim tests passed unless they were actually run.

## 12. Background Jobs and External Integrations

- Use a durable job queue for critical or retryable asynchronous work such as report generation, notification delivery, and integration processing.
- Background jobs must be idempotent, observable, retry-aware, and safe under duplicate delivery.
- Use an outbox pattern when a committed business transaction must reliably publish an event.
- Keep payment, shipping, email, and object-storage integrations behind interfaces/adapters.
- Use timeouts, bounded retries, backoff, and dead-letter/failed-job handling where supported.
- Never make a successful financial posting depend solely on an unconfirmed external API call.

## 13. Observability and Operations

- Emit structured logs with request/correlation IDs.
- Add health/readiness endpoints that do not expose secrets or internal diagnostics.
- Record metrics for request latency, error rates, cache hit/miss rates, queue depth, database pool health, and critical business workflows where possible.
- Use explicit database connection-pool settings suitable for worker count and database limits.
- Run migrations as a controlled deployment step, not independently in every application worker at startup.
- Provide Docker-based local development where appropriate and production configuration through environment variables.
- Keep frontend and backend deployment configuration separate unless intentionally deploying them together.
- Document backups, restore drills, migration rollback strategy, retention, and disaster recovery for financial records.

## 14. Implementation Workflow for AI Agents

Before coding:

1. Inspect repository structure, dependency files, conventions, and existing tests.
2. Identify the owning business module and its public interfaces.
3. Trace related models, services, repositories, migrations, API schemas, frontend services, and query keys.
4. Check company/fiscal-year scoping, permissions, audit requirements, transaction boundaries, and cache effects.
5. Write a brief implementation plan for cross-module or financially significant changes.

While coding:

- Prefer small, reviewable changes that follow existing patterns.
- Reuse established shared infrastructure.
- Avoid unrelated refactors and speculative abstractions.
- Do not bypass services by directly modifying another module's tables from a router.
- Do not mutate posted accounting entries or stock movements silently.
- Do not add caching without an explicit consistency and invalidation plan.
- Do not introduce breaking API changes without documenting them.
- Add or update tests alongside behavior changes.

After coding:

- Run relevant backend and frontend checks.
- Summarize files changed, behavior added, migrations, tests run, and known limitations.
- Clearly identify any decisions that require product or accounting-policy confirmation.
- Never invent credentials, environment values, provider capabilities, or test results.

## 15. Suggested Delivery Phases

Implement incrementally, with each phase producing tested, usable functionality.

1. **Foundation:** repository setup, configuration, database, migrations, logging, API error format, authentication, authorization, company context, frontend shell, API client, and test infrastructure.
2. **Company and accounting foundation:** fiscal years, accounting periods, chart of accounts, document numbering, audit trail, and opening balances.
3. **Master data:** products, units, categories, customers, vendors, warehouses, and storage locations.
4. **Purchasing and inventory:** purchase orders, goods receipts, stock ledger, transfers, counts, adjustments, and costing policy.
5. **Sales and e-commerce:** catalog, pricing, cart, checkout, order lifecycle, reservations, and payment integration.
6. **Invoicing and accounting integration:** invoices, receipts, vendor bills, payments, balanced journal posting, receivables, and payables.
7. **Fulfillment and delivery:** picking, packing, dispatch, tracking, proof of delivery, failed delivery, and returns.
8. **Reports and controls:** financial statements, stock valuation, operational reports, exports, permissions, and audit review.
9. **Performance and production readiness:** cache policy, file/object storage, background jobs, observability, security review, load tests, backup/restore, and deployment automation.

Do not implement all phases in one large change. Confirm unresolved accounting policies, tax requirements, costing method, authentication strategy, and payment/shipping providers before those decisions become embedded in the schema or posting logic.

## 16. Definition of Done

A feature is complete only when:

- Business behavior and acceptance criteria are satisfied.
- API schemas, authorization, company/fiscal-year scoping, and errors are correct.
- Database constraints and migrations are included when needed.
- Service/repository boundaries and transaction behavior are correct.
- Frontend service, query keys, invalidation, forms, and UI states are implemented where applicable.
- Cache behavior is safe and documented if caching is involved.
- Audit trail and accounting/stock effects are correct where applicable.
- Relevant automated tests pass.
- Documentation and generated contracts are updated where needed.
- Known limitations and assumptions are disclosed.

## 17. Non-Negotiable Invariants

1. Posted journal entries balance.
2. Posted accounting and stock history is not silently overwritten or deleted.
3. Company and fiscal-year access is validated server-side.
4. Critical multi-step operations use deliberate transaction boundaries.
5. Retries cannot duplicate payments, orders, stock movements, or financial postings.
6. Backend values are authoritative for prices, taxes, totals, balances, and stock.
7. Cache keys and invalidation preserve company, fiscal-year, user, and permission boundaries.
8. Private files are never publicly accessible by default.
9. External webhooks and asynchronous jobs are authenticated where applicable and idempotent.
10. Accounting, tax, and legal behavior must be confirmed against the intended jurisdiction and business requirements before production use.
