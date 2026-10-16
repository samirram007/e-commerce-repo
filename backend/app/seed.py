"""Seed demo data: run `python -m app.seed` (or via docker-compose) after
migrations. Creates the platform admin, a demo company with its chart of
accounts and fiscal year, a warehouse, and sample master data.
"""
import logging

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.accounting.service import create_default_chart
from app.modules.catalog import service as catalog
from app.modules.companies import service as companies
from app.modules.fiscal_years import service as fiscal
from app.modules.identity import service as identity
from app.modules.partners import service as partners
from app.modules.storage import service as storage
from app.modules.taxes import service as taxes

logger = logging.getLogger("erp.seed")


def run_seed() -> None:
    settings = get_settings()
    factory = get_session_factory()
    session = factory()
    try:
        if not identity.has_any_user(session):
            admin = identity.bootstrap_platform_admin(
                session,
                email=settings.seed_admin_email,
                password=settings.seed_admin_password,
                full_name="Platform Admin",
            )
            logger.info("created platform admin %s", admin.email)
        else:
            admin = identity.get_by_email(session, settings.seed_admin_email)
            if admin is None:
                # first existing user becomes the seed actor
                from sqlalchemy import select
                from app.modules.identity.models import User

                admin = session.execute(select(User).order_by(User.created_at)).scalars().first()
        identity.ensure_system_roles(session)
        session.commit()

        company = None
        for c in companies.list_companies_for_user(session, admin.id):
            company = c
            break
        created_company = False
        if company is None and settings.seed_demo_data:
            company = companies.create_company(
                session,
                name="Demo Retail Co",
                legal_name="Demo Retail Company Ltd",
                base_currency="USD",
                owner_user_id=admin.id,
            )
            created_company = True
        session.commit()

        if settings.seed_demo_data:
            # fiscal year covering this and the next calendar year
            from datetime import date

            fy = fiscal.resolve_fiscal_year(session, company_id=company.id, on_date=date.today())
            if fy is None:
                fiscal.create_fiscal_year(
                    session,
                    company_id=company.id,
                    start_date=date(date.today().year, 1, 1),
                    end_date=date(date.today().year + 1, 12, 31),
                    actor_user_id=admin.id,
                )
            create_default_chart(session, company=company)
            if taxes.default_sales_tax_id(session, company.id) is None:
                session.commit()
                from app.modules.taxes.models import TaxRate

                session.add(
                    TaxRate(
                        company_id=company.id,
                        code="VAT10",
                        name="Sales VAT 10%",
                        percentage=10,
                        is_default_sales=True,
                        is_default_purchase=True,
                        created_by=admin.id,
                    )
                )
            demo_warehouse = None
            for loc in storage.list_locations(session, company.id, location_type="warehouse"):
                demo_warehouse = loc
                break
            if demo_warehouse is None:
                wh = storage.create_location(
                    session, company_id=company.id, actor_user_id=admin.id, code="WH-MAIN", name="Main Warehouse", location_type="warehouse"
                )
                zone = storage.create_location(session, company_id=company.id, actor_user_id=admin.id, code="Z1", name="Zone 1", location_type="zone", parent_id=wh.id)
                bin1 = storage.create_location(session, company_id=company.id, actor_user_id=admin.id, code="Z1-B1", name="Bin 1", location_type="bin", parent_id=zone.id)
                _ = bin1
            if created_company:
                for sku, name, cost, price in [
                    ("SKU-001", "Demo Widget Small", 8.0, 19.99),
                    ("SKU-002", "Demo Widget Large", 14.5, 34.9),
                    ("SKU-SVC", "Delivery Service", 0, 9.99),
                ]:
                    if not catalog.list_products(session, company.id, search=sku):
                        catalog.create_product(
                            session,
                            company_id=company.id,
                            actor_user_id=admin.id,
                            data={
                                "sku": sku,
                                "name": name,
                                "stock_type": "service" if sku.endswith("SVC") else "stock",
                                "base_cost": str(cost),
                                "base_price": str(price),
                                "is_sellable": True,
                            },
                        )
                partners.create_customer(
                    session, company_id=company.id, actor_user_id=admin.id,
                    data={"code": "C-001", "name": "Demo Customer", "email": "customer@example.com"},
                )
                partners.create_vendor(
                    session, company_id=company.id, actor_user_id=admin.id,
                    data={"code": "V-001", "name": "Demo Vendor", "email": "vendor@example.com"},
                )
            session.commit()
        logger.info("seed complete")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
