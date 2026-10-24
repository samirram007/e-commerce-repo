"""API router aggregation; mounted under /api/v1 by app.main"""
from fastapi import APIRouter

from app.modules.accounting.router import router as accounting_router
from app.modules.audit.router import router as audit_router
from app.modules.catalog.router import router as catalog_router
from app.modules.companies.router import router as companies_router
from app.modules.fiscal_years.router import router as fiscal_router
from app.modules.fulfillment.router import router as fulfillment_router
from app.modules.identity.router import router as identity_router
from app.modules.inventory.router import router as inventory_router
from app.modules.invoicing.router import router as invoicing_router
from app.modules.partners.router import router as partners_router
from app.modules.payments.router import router as payments_router
from app.modules.payroll.router import router as payroll_router
from app.modules.periods.router import router as periods_router
from app.modules.purchasing.router import router as purchasing_router
from app.modules.reports.router import router as reports_router
from app.modules.returns.router import router as returns_router
from app.modules.sales.router import router as sales_router
from app.modules.storage.router import router as storage_router
from app.modules.storefront.admin_router import router as storefront_admin_router
from app.modules.storefront.router import router as storefront_router
from app.modules.taxes.router import router as taxes_router

api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(companies_router)
api_router.include_router(fiscal_router)
api_router.include_router(accounting_router, prefix="/accounting")
api_router.include_router(taxes_router)
api_router.include_router(catalog_router, prefix="/catalog")
api_router.include_router(partners_router, prefix="/partners")
api_router.include_router(storage_router)
api_router.include_router(inventory_router)
api_router.include_router(purchasing_router)
api_router.include_router(sales_router)
api_router.include_router(storefront_router)
api_router.include_router(invoicing_router)
api_router.include_router(payments_router)
api_router.include_router(payroll_router)
api_router.include_router(fulfillment_router)
api_router.include_router(returns_router)
api_router.include_router(reports_router)
api_router.include_router(periods_router)
api_router.include_router(audit_router)
api_router.include_router(storefront_router)
api_router.include_router(storefront_admin_router)
