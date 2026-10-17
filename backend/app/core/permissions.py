"""Permission catalogue and authorization dependency.

Permissions are dotted strings per module. Roles cluster permissions; users are
granted roles per company (identity module). Enforced server-side on every
protected endpoint via `require_permission`.
Permission checks include company context resolved by `current_company_ctx`
before this dependency in the router chain.
"""
from fastapi import Depends

from app.core.exceptions import ForbiddenError

# Platform-level (not company scoped)
PERMISSION_VIEW_AUDIT_LOG = "audit.log.read"
PERMISSION_MANAGE_USERS = "platform.users.manage"

# Company-level
P_ACCOUNTS_MANAGE = "accounting.accounts.manage"
P_JOURNAL_POST = "accounting.journal.post"
P_JOURNAL_VIEW = "accounting.journal.view"
P_REPORTS_VIEW = "reports.view"
P_FISCAL_MANAGE = "fiscal.manage"
P_CATALOG_MANAGE = "catalog.manage"
P_CATALOG_VIEW = "catalog.view"
P_PARTNERS_MANAGE = "partners.manage"
P_SALES_ORDER_CREATE = "sales.order.create"
P_SALES_VIEW = "sales.view"
P_SALES_FULFILL = "sales.fulfill"
P_PURCHASE_CREATE = "purchasing.po.create"
P_PURCHASE_APPROVE = "purchasing.po.approve"
P_PURCHASE_VIEW = "purchasing.view"
P_BILL_MANAGE = "purchasing.bill.manage"
P_INVENTORY_MANAGE = "inventory.manage"
P_INVENTORY_VIEW = "inventory.view"
P_INVOICES_MANAGE = "invoicing.manage"
P_INVOICES_VIEW = "invoicing.view"
P_PAYMENTS_MANAGE = "payments.manage"
P_PAYMENTS_VIEW = "payments.view"
P_RETURNS_MANAGE = "returns.manage"
P_STORAGE_MANAGE = "storage.manage"
P_COMPANY_SETTINGS = "company.settings.manage"
P_MEMBERS_MANAGE = "company.members.manage"
P_FILES_UPLOAD = "files.upload"
P_CART_CHECKOUT = "storefront.cart.use"
P_PAYROLL_MANAGE = "payroll.manage"
P_PAYROLL_VIEW = "payroll.view"

ALL_PERMISSIONS: dict[str, str] = {
    PERMISSION_VIEW_AUDIT_LOG: "View audit log",
    PERMISSION_MANAGE_USERS: "Manage platform users/roles",
    P_ACCOUNTS_MANAGE: "Manage chart of accounts",
    P_JOURNAL_POST: "Post/reverse journal entries",
    P_JOURNAL_VIEW: "View journal entries",
    P_REPORTS_VIEW: "View reports",
    P_FISCAL_MANAGE: "Manage fiscal years/periods",
    P_CATALOG_MANAGE: "Manage product catalog",
    P_CATALOG_VIEW: "View product catalog",
    P_PARTNERS_MANAGE: "Manage customers and vendors",
    P_SALES_ORDER_CREATE: "Create sales orders/checkout",
    P_SALES_VIEW: "View sales orders",
    P_SALES_FULFILL: "Fulfill/deliver sales orders",
    P_PURCHASE_CREATE: "Create purchase orders",
    P_PURCHASE_APPROVE: "Approve purchase orders",
    P_PURCHASE_VIEW: "View purchasing",
    P_BILL_MANAGE: "Manage vendor bills/receipts",
    P_INVENTORY_MANAGE: "Adjust/transfer stock, counts",
    P_INVENTORY_VIEW: "View stock and ledger",
    P_INVOICES_MANAGE: "Create/post/reverse invoices",
    P_INVOICES_VIEW: "View invoices/credit notes",
    P_PAYMENTS_MANAGE: "Record/allocate payments",
    P_PAYMENTS_VIEW: "View payments",
    P_RETURNS_MANAGE: "Manage returns/refunds",
    P_STORAGE_MANAGE: "Manage warehouses/locations",
    P_COMPANY_SETTINGS: "Manage company settings",
    P_MEMBERS_MANAGE: "Manage company members",
    P_FILES_UPLOAD: "Upload files",
    P_CART_CHECKOUT: "Use storefront cart/checkout",
    P_PAYROLL_MANAGE: "Manage employees and payroll runs",
    P_PAYROLL_VIEW: "View payroll and payslips",
}

# ---- permission groups used to compose role templates ----
# Everything company-scoped (i.e. all permissions except the two platform-level ones).
COMPANY_PERMISSIONS: list[str] = [
    P_ACCOUNTS_MANAGE, P_JOURNAL_POST, P_JOURNAL_VIEW, P_REPORTS_VIEW,
    P_FISCAL_MANAGE, P_CATALOG_MANAGE, P_CATALOG_VIEW, P_PARTNERS_MANAGE,
    P_SALES_ORDER_CREATE, P_SALES_VIEW, P_SALES_FULFILL, P_PURCHASE_CREATE,
    P_PURCHASE_APPROVE, P_PURCHASE_VIEW, P_BILL_MANAGE, P_INVENTORY_MANAGE,
    P_INVENTORY_VIEW, P_INVOICES_MANAGE, P_INVOICES_VIEW, P_PAYMENTS_MANAGE,
    P_PAYMENTS_VIEW, P_RETURNS_MANAGE, P_STORAGE_MANAGE, P_COMPANY_SETTINGS,
    P_MEMBERS_MANAGE, P_FILES_UPLOAD, P_CART_CHECKOUT,
    P_PAYROLL_MANAGE, P_PAYROLL_VIEW,
]

# Read-only subset used by the "Other User" tier.
READ_ONLY_PERMISSIONS: list[str] = [
    P_CATALOG_VIEW, P_INVENTORY_VIEW, P_SALES_VIEW, P_PURCHASE_VIEW,
    P_INVOICES_VIEW, P_PAYMENTS_VIEW, P_REPORTS_VIEW, P_PAYROLL_VIEW,
]

# Assignable user tiers (Developer / Admin / Other User).
USER_TIER_ROLES: tuple[str, ...] = ("developer", "admin", "other_user")

# Roles that grant elevated access. Only a company admin or an existing holder of
# one of these may assign them (privilege-escalation guard in the companies router).
PRIVILEGED_ROLES: tuple[str, ...] = ("developer", "admin")

ROLE_LABELS: dict[str, str] = {
    "platform_admin": "Platform Admin",
    "company_admin": "Company Admin",
    "accountant": "Accountant",
    "inventory_manager": "Inventory Manager",
    "sales_agent": "Sales Agent",
    "purchasing_agent": "Purchasing Agent",
    "fulfillment_agent": "Fulfillment Agent",
    "developer": "Developer",
    "admin": "Admin",
    "other_user": "Other User",
}


def role_label(name: str) -> str:
    return ROLE_LABELS.get(name, name.replace("_", " ").title())


ROLE_TEMPLATES: dict[str, list[str]] = {
    "platform_admin": [PERMISSION_MANAGE_USERS, PERMISSION_VIEW_AUDIT_LOG],
    # company owner: everything; app_superuser grants * within company
    "company_admin": [],  # handled via is_company_admin flag
    "accountant": [
        P_ACCOUNTS_MANAGE, P_JOURNAL_POST, P_JOURNAL_VIEW, P_REPORTS_VIEW,
        P_FISCAL_MANAGE, P_INVOICES_MANAGE, P_INVOICES_VIEW, P_PAYMENTS_MANAGE,
        P_PAYMENTS_VIEW, P_RETURNS_MANAGE, P_INVENTORY_VIEW, P_SALES_VIEW, P_PURCHASE_VIEW,
        P_PAYROLL_MANAGE, P_PAYROLL_VIEW,
    ],
    "inventory_manager": [
        P_INVENTORY_MANAGE, P_INVENTORY_VIEW, P_CATALOG_MANAGE, P_CATALOG_VIEW,
        P_STORAGE_MANAGE, P_REPORTS_VIEW,
    ],
    "sales_agent": [
        P_CATALOG_VIEW, P_CART_CHECKOUT, P_SALES_ORDER_CREATE, P_SALES_VIEW,
        P_PARTNERS_MANAGE, P_SALES_FULFILL,
    ],
    "purchasing_agent": [
        P_CATALOG_VIEW, P_PURCHASE_CREATE, P_PURCHASE_VIEW, P_BILL_MANAGE, P_PARTNERS_MANAGE,
    ],
    "fulfillment_agent": [P_SALES_FULFILL, P_INVENTORY_VIEW, P_CATALOG_VIEW],
    # ---- assignable user tiers ----
    "developer": COMPANY_PERMISSIONS + [PERMISSION_MANAGE_USERS, PERMISSION_VIEW_AUDIT_LOG],
    "admin": COMPANY_PERMISSIONS,
    "other_user": READ_ONLY_PERMISSIONS,
}


def require_permission(*perms: str):
    """Dependency that checks the resolved permission context stored on request.state."""

    from app.modules.identity.dependencies import require_permissions  # late import

    return Depends(require_permissions(perms))
