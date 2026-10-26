"""Seed demo data: run `python -m app.seed` (or via docker-compose) after
migrations. Creates the platform admin, a demo company with its chart of
accounts and fiscal year, a warehouse, and sample master data.

The demo layer (users, catalog, partners, stock, orders, shipments) is
idempotent and re-runnable: every entity is guarded by a natural key
(email, SKU, customer code, order marker), so `python -m app.seed` tops up an
existing database instead of duplicating it.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.accounting.service import create_default_chart
from app.modules.catalog import service as catalog
from app.modules.companies import service as companies
from app.modules.fiscal_years import service as fiscal
from app.modules.identity import service as identity
from app.modules.partners import service as partners
from app.modules.payroll import service as payroll
from app.modules.storage import service as storage

logger = logging.getLogger("erp.seed")

#: Name of the demo company the seed tops up (never a leftover test company).
DEMO_COMPANY_NAME = "Demo Retail Co"


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

        # A dev database may hold leftover test companies owned by the same
        # admin; always top up the demo company when it exists.
        candidates = companies.list_companies_for_user(session, admin.id)
        company = next((c for c in candidates if c.name == DEMO_COMPANY_NAME), None)
        if company is None and candidates:
            company = candidates[0]
        created_company = False
        if company is None and settings.seed_demo_data:
            company = companies.create_company(
                session,
                name=DEMO_COMPANY_NAME,
                legal_name="Demo Retail Company Ltd",
                base_currency="INR",
                owner_user_id=admin.id,
            )
            created_company = True
        session.commit()

        # Currency + public storefront settings for the demo company.
        companies.ensure_currency(session, "INR", "Indian Rupee")
        logger.info("seeding company %s (%s)", company.name, company.id)
        if not company.storefront_slug:
            company.storefront_slug = "default"
        # invoice header details (printed on the GST invoice); demo values only
        if not company.address:
            company.address = "12 MG Road, Bengaluru, Karnataka 560001, India"
        if not company.tax_identifier:
            company.tax_identifier = "29ABCDE1234F1Z5"
        company.allow_guest_checkout = True
        if (company.base_currency or "").upper() != "INR":
            company.base_currency = "INR"
        session.flush()

        if settings.seed_demo_data:
            # fiscal year covering this and the next calendar year
            fy = fiscal.resolve_fiscal_year(session, company_id=company.id, on_date=date.today())
            if fy is None:
                fiscal.create_fiscal_year(
                    session,
                    company_id=company.id,
                    start_date=date(date.today().year, 1, 1),
                    end_date=date(date.today().year + 1, 12, 31),
                    actor_user_id=admin.id,
                )
                fy = fiscal.resolve_fiscal_year(session, company_id=company.id, on_date=date.today())
            create_default_chart(session, company=company)
            _seed_taxes(session, company, admin)
            demo_warehouse = None
            for loc in storage.list_locations(session, company.id):
                if loc.location_type in storage.FACILITY_TYPES:
                    demo_warehouse = loc
                    break
            if demo_warehouse is None:
                wh = storage.create_location(
                    session, company_id=company.id, actor_user_id=admin.id, code="WH-MAIN", name="Main Warehouse", location_type="warehouse"
                )
                zone = storage.create_location(session, company_id=company.id, actor_user_id=admin.id, code="Z1", name="Zone 1", location_type="zone", parent_id=wh.id)
                bin1 = storage.create_location(session, company_id=company.id, actor_user_id=admin.id, code="Z1-B1", name="Bin 1", location_type="bin", parent_id=zone.id)
                _ = bin1
            demo_bin = next(
                (loc for loc in storage.list_locations(session, company.id) if loc.location_type == "bin"),
                None,
            )
            if demo_bin is None and demo_warehouse is not None:
                zone = storage.create_location(
                    session, company_id=company.id, actor_user_id=admin.id,
                    code="Z1", name="Zone 1", location_type="zone", parent_id=demo_warehouse.id,
                )
                demo_bin = storage.create_location(
                    session, company_id=company.id, actor_user_id=admin.id,
                    code="Z1-B1", name="Bin 1", location_type="bin", parent_id=zone.id,
                )

            # Idempotent demo layer: runs on first seed AND on top-ups.
            _seed_demo_users(session, company, admin, settings.seed_admin_password)
            _seed_demo_catalog(session, company, admin)
            _seed_demo_partners(session, company, admin)
            _seed_storefront_zones(session, company, admin)
            # public storefront content (categories/products/hero/faqs/policies)
            from app.seed_data.storefront import seed_storefront

            seed_storefront(session, company, admin)

            if created_company:
                # demo payroll: three employees + a draft run for the current month
                if not payroll.list_employees(session, company.id):
                    for code, first, last, salary, allowances, deduction in [
                        ("E-001", "Demo", "Manager", "4500.00", "200.00", "10"),
                        ("E-002", "Sample", "Clerk", "2800.00", "100.00", "8"),
                        ("E-003", "Test", "Worker", "2200.00", "0", "5"),
                    ]:
                        payroll.create_employee(
                            session, company_id=company.id, actor_user_id=admin.id,
                            data={
                                "employee_code": code,
                                "first_name": first,
                                "last_name": last,
                                "job_title": "Demo Staff",
                                "base_salary": salary,
                                "allowances": allowances,
                                "deduction_rate": deduction,
                            },
                        )
                    today = date.today()
                    existing = [
                        r
                        for r in payroll.list_runs(session, company.id)
                        if r.period_year == today.year
                        and r.period_month == today.month
                        and r.status != "cancelled"
                    ]
                    if not existing:
                        payroll.run_payroll(
                            session,
                            company_id=company.id,
                            actor_user_id=admin.id,
                            period_year=today.year,
                            period_month=today.month,
                        )
                        logger.info(
                            "seeded draft payroll run %d-%02d",
                            today.year,
                            today.month,
                        )

            _seed_demo_stock(session, company, admin, demo_bin)
            _seed_demo_orders(session, company, admin, floor_date=fy.start_date)
            session.commit()
        logger.info("seed complete")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_demo_users(session, company, admin, password: str) -> None:
    """Demo logins across every role so the users list (search, status and
    role filters) and permission-scoped screens have real data to chew on."""
    from sqlalchemy import select

    from app.modules.identity.models import UserCompany

    demo_users = [
        # (email, full_name, is_platform_admin, role_names, is_company_admin, is_active)
        ("root@demo.example.com", "Robin Root", True, ["admin"], True, True),
        ("manager@demo.example.com", "Maya Manager", False, ["admin"], False, True),
        ("accountant@demo.example.com", "Aaron Accountant", False, ["accountant"], False, True),
        ("sales1@demo.example.com", "Sofia Sales", False, ["sales_agent"], False, True),
        ("sales2@demo.example.com", "Sam Salesman", False, ["sales_agent"], False, True),
        ("inventory@demo.example.com", "Ivan Inventory", False, ["inventory_manager"], False, True),
        ("purchasing@demo.example.com", "Priya Purchasing", False, ["purchasing_agent"], False, True),
        ("fulfillment@demo.example.com", "Felix Fulfillment", False, ["fulfillment_agent"], False, True),
        ("viewer@demo.example.com", "Vera Viewer", False, ["other_user"], False, True),
        ("contractor@demo.example.com", "Chris Contractor", False, ["other_user"], False, False),
    ]
    created = 0
    for email, full_name, is_platform_admin, role_names, is_company_admin, is_active in demo_users:
        user = identity.get_by_email(session, email)
        if user is None:
            user = identity.create_user(
                session,
                email=email,
                password=password,
                full_name=full_name,
                is_platform_admin=is_platform_admin,
            )
            created += 1
        if not is_active:
            user.is_active = False
        membership = session.scalar(
            select(UserCompany).where(
                UserCompany.user_id == user.id, UserCompany.company_id == company.id
            )
        )
        if membership is None:
            companies.grant_membership(
                session,
                company_id=company.id,
                user_id=user.id,
                is_company_admin=is_company_admin,
                role_names=role_names,
            )
    if created:
        logger.info("seeded %d demo users (password: %s)", created, password)


# (sku, name, category_path, uom, stock_type, cost, price, barcode, batches, serials, active, sellable, purchasable)
#: HSN (goods) / SAC (services) code per demo leaf category, printed on GST invoices.
_HSN_BY_CATEGORY = {
    "Electronics": "8517",
    "Phones": "8517",
    "Laptops": "8471",
    "Accessories": "8473",
    "Apparel": "6109",
    "Home & Kitchen": "7323",
    "Grocery": "2106",
    "Services": "9987",
}

_DEMO_PRODUCTS = [
    # original three (kept identical so existing databases match)
    ("SKU-001", "Demo Widget Small", ("Accessories",), "PCS", "stock", "8.00", "19.99", "8901234000011", False, False, True, True, True),
    ("SKU-002", "Demo Widget Large", ("Accessories",), "PCS", "stock", "14.50", "34.90", "8901234000028", False, False, True, True, True),
    ("SKU-SVC", "Delivery Service", ("Services",), "HR", "service", "0", "9.99", None, False, False, True, True, False),
    # phones (serial-tracked flagships + a plain model)
    ("SKU-PHX-001", "Nova X Phone 128GB", ("Electronics", "Phones"), "PCS", "stock", "320.00", "499.00", "8901234000035", False, True, True, True, True),
    ("SKU-PHX-002", "Nova X Phone 256GB", ("Electronics", "Phones"), "PCS", "stock", "390.00", "599.00", "8901234000042", False, True, True, True, True),
    ("SKU-PHX-003", "Pixelmate A1 Phone", ("Electronics", "Phones"), "PCS", "stock", "120.00", "199.00", "8901234000059", False, False, True, True, True),
    # laptops
    ("SKU-LAP-001", "ZenBook 14 Laptop", ("Electronics", "Laptops"), "PCS", "stock", "650.00", "899.00", "8901234000066", False, True, True, True, True),
    ("SKU-LAP-002", "ThinkPad Pro 15 Laptop", ("Electronics", "Laptops"), "PCS", "stock", "950.00", "1299.00", "8901234000073", False, True, True, True, True),
    ("SKU-LAP-003", "Chromebook Go 11", ("Electronics", "Laptops"), "PCS", "stock", "150.00", "249.00", "8901234000080", False, False, True, True, True),
    # accessories
    ("SKU-ACC-001", "USB-C Cable 1m", ("Electronics", "Accessories"), "PCS", "stock", "4.50", "12.99", "8901234000097", False, False, True, True, True),
    ("SKU-ACC-002", "Wireless Mouse", ("Electronics", "Accessories"), "PCS", "stock", "12.00", "29.50", "8901234000103", False, False, True, True, True),
    ("SKU-ACC-003", 'Laptop Sleeve 14"', ("Electronics", "Accessories"), "PCS", "stock", "7.00", "19.99", None, False, False, True, True, True),
    ("SKU-ACC-004", "65W USB-C Charger", ("Electronics", "Accessories"), "PCS", "stock", "16.00", "39.99", "8901234000110", False, False, True, True, True),
    ("SKU-ACC-005", "Screen Protector Pack", ("Electronics", "Accessories"), "BOX", "stock", "1.80", "9.50", None, False, False, True, True, True),
    ("SKU-ACC-006", "Bluetooth Earbuds", ("Electronics", "Accessories"), "PCS", "stock", "35.00", "79.99", "8901234000127", False, False, False, True, True),
    ("SKU-ACC-007", "Internal Component Kit", ("Electronics", "Accessories"), "BOX", "stock", "22.00", "0.00", None, False, False, True, False, True),
    # apparel
    ("SKU-APP-001", "Cotton T-Shirt M", ("Apparel",), "PCS", "stock", "5.00", "14.99", "8901234000134", False, False, True, True, True),
    ("SKU-APP-002", "Cotton T-Shirt L", ("Apparel",), "PCS", "stock", "5.00", "14.99", "8901234000141", False, False, True, True, True),
    ("SKU-APP-003", "Denim Jeans", ("Apparel",), "PCS", "stock", "18.00", "44.99", "8901234000158", False, False, True, True, True),
    ("SKU-APP-004", "Running Shoes Size 9", ("Apparel",), "PCS", "stock", "30.00", "69.99", "8901234000165", False, False, True, True, True),
    ("SKU-APP-005", "Wool Beanie", ("Apparel",), "PCS", "stock", "3.50", "12.50", None, False, False, True, True, True),
    # home & kitchen
    ("SKU-HOM-001", "Stainless Kettle 1.7L", ("Home & Kitchen",), "PCS", "stock", "22.00", "49.99", "8901234000172", False, False, True, True, True),
    ("SKU-HOM-002", "Non-Stick Pan 28cm", ("Home & Kitchen",), "PCS", "stock", "14.00", "34.50", "8901234000189", False, False, True, True, True),
    ("SKU-HOM-003", "LED Desk Lamp", ("Home & Kitchen",), "PCS", "stock", "11.00", "27.99", None, False, False, True, True, True),
    ("SKU-HOM-004", "Storage Box 40L", ("Home & Kitchen",), "PCS", "stock", "6.00", "18.99", None, False, False, True, True, True),
    ("SKU-HOM-005", "Coffee Mug Set of 4", ("Home & Kitchen",), "BOX", "stock", "9.00", "24.99", "8901234000196", False, False, True, True, True),
    # grocery (batch-tracked with expiry)
    ("SKU-GRV-001", "Arabica Coffee Beans 1kg", ("Grocery",), "KG", "stock", "9.00", "18.99", "8901234000202", True, False, True, True, True),
    ("SKU-GRV-002", "Green Tea 100 Bags", ("Grocery",), "BOX", "stock", "3.20", "8.99", None, True, False, True, True, True),
    ("SKU-GRV-003", "Olive Oil 500ml", ("Grocery",), "PCS", "stock", "5.50", "12.50", "8901234000219", True, False, True, True, True),
    ("SKU-GRV-004", "Basmati Rice 5kg", ("Grocery",), "BAG", "stock", "8.00", "16.99", None, True, False, True, True, True),
    # services
    ("SKU-SVC-002", "Installation Service", ("Services",), "HR", "service", "0", "49.00", None, False, False, True, True, False),
    ("SKU-SVC-003", "Extended Warranty 1 Year", ("Services",), "PCS", "service", "0", "79.00", None, False, False, True, True, False),
    ("SKU-SVC-004", "Gift Wrapping", ("Services",), "PCS", "service", "0", "4.99", None, False, False, True, True, False),
    # audio
    ("SKU-AUD-001", "Studio Over-Ear Headphones", ("Electronics", "Audio"), "PCS", "stock", "55.00", "129.00", "8901234000226", False, False, True, True, True),
    ("SKU-AUD-002", "Smart Speaker Mini", ("Electronics", "Audio"), "PCS", "stock", "28.00", "69.99", "8901234000233", False, False, True, True, True),
    ("SKU-AUD-003", "Soundbar 2.1 Channel", ("Electronics", "Audio"), "PCS", "stock", "70.00", "159.00", "8901234000240", False, False, True, True, True),
    # wearables
    ("SKU-WER-001", "Pulse Smartwatch 44mm", ("Electronics", "Wearables"), "PCS", "stock", "90.00", "199.00", "8901234000257", False, True, True, True, True),
    ("SKU-WER-002", "Fitness Band Lite", ("Electronics", "Wearables"), "PCS", "stock", "18.00", "49.99", "8901234000264", False, False, True, True, True),
    ("SKU-WER-003", "Wireless Charge Dock", ("Electronics", "Wearables"), "PCS", "stock", "15.00", "39.99", None, False, False, True, True, True),
    # cameras
    ("SKU-CAM-001", "Action Cam 4K", ("Electronics", "Cameras"), "PCS", "stock", "120.00", "249.00", "8901234000271", False, True, True, True, True),
    ("SKU-CAM-002", "Tripod 160cm", ("Electronics", "Cameras"), "PCS", "stock", "12.00", "29.99", None, False, False, True, True, True),
    ("SKU-CAM-003", "64GB SD Card", ("Electronics", "Cameras"), "PCS", "stock", "6.00", "17.99", "8901234000288", False, False, True, True, True),
    # tablets
    ("SKU-TAB-001", "Nova Tab 11", ("Electronics", "Tablets"), "PCS", "stock", "210.00", "399.00", "8901234000295", False, True, True, True, True),
    ("SKU-TAB-002", "Kids Tab 8", ("Electronics", "Tablets"), "PCS", "stock", "80.00", "149.00", "8901234000301", False, False, True, True, True),
    # sports & outdoors
    ("SKU-SPT-001", "Yoga Mat 6mm", ("Sports & Outdoors",), "PCS", "stock", "9.00", "24.99", None, False, False, True, True, True),
    ("SKU-SPT-002", "Insulated Water Bottle 1L", ("Sports & Outdoors",), "PCS", "stock", "7.00", "21.99", "8901234000318", False, False, True, True, True),
    ("SKU-SPT-003", "Camping Lantern", ("Sports & Outdoors",), "PCS", "stock", "11.00", "26.99", None, False, False, True, True, True),
    ("SKU-FIT-001", "Adjustable Dumbbell 20kg", ("Sports & Outdoors", "Fitness"), "PCS", "stock", "45.00", "109.00", "8901234000325", False, False, True, True, True),
    ("SKU-FIT-002", "Resistance Band Set", ("Sports & Outdoors", "Fitness"), "BOX", "stock", "5.00", "16.99", None, False, False, True, True, True),
    ("SKU-FIT-003", "Foam Roller", ("Sports & Outdoors", "Fitness"), "PCS", "stock", "6.00", "18.99", None, False, False, True, True, True),
    ("SKU-CYC-001", "Bike Helmet M", ("Sports & Outdoors", "Cycling"), "PCS", "stock", "22.00", "54.99", "8901234000332", False, False, True, True, True),
    ("SKU-CYC-002", "Bike Light Set", ("Sports & Outdoors", "Cycling"), "BOX", "stock", "8.00", "22.99", None, False, False, True, True, True),
    # beauty & personal care (batch-tracked with expiry)
    ("SKU-BTY-001", "Vitamin C Serum 30ml", ("Beauty & Personal Care",), "PCS", "stock", "6.00", "21.99", "8901234000349", True, False, True, True, True),
    ("SKU-BTY-002", "Daily Sunscreen SPF50", ("Beauty & Personal Care",), "PCS", "stock", "5.00", "17.99", "8901234000356", True, False, True, True, True),
    ("SKU-SKN-001", "Aloe Face Wash 150ml", ("Beauty & Personal Care", "Skincare"), "PCS", "stock", "3.20", "11.99", None, True, False, True, True, True),
    ("SKU-SKN-002", "Hydrating Night Cream", ("Beauty & Personal Care", "Skincare"), "PCS", "stock", "7.50", "24.99", "8901234000363", True, False, True, True, True),
    # toys & games
    ("SKU-TOY-001", "Wooden Puzzle Set", ("Toys & Games",), "BOX", "stock", "7.00", "19.99", None, False, False, True, True, True),
    ("SKU-TOY-002", "RC Car 1:18", ("Toys & Games",), "PCS", "stock", "16.00", "39.99", "8901234000370", False, False, True, True, True),
    # stationery
    ("SKU-STN-001", "A5 Dotted Notebook", ("Stationery",), "PCS", "stock", "3.00", "9.99", None, False, False, True, True, True),
    ("SKU-STN-002", "Gel Pen Pack of 10", ("Stationery",), "BOX", "stock", "1.60", "6.99", None, False, False, True, True, True),
    ("SKU-STN-003", "Desk Organiser", ("Stationery",), "PCS", "stock", "8.00", "22.99", "8901234000387", False, False, True, True, True),
    # grocery: beverages & snacks (batch-tracked)
    ("SKU-GRV-005", "Cold Brew Concentrate 500ml", ("Grocery", "Beverages"), "PCS", "stock", "4.50", "11.99", "8901234000394", True, False, True, True, True),
    ("SKU-GRV-006", "Sparkling Water 6 Pack", ("Grocery", "Beverages"), "BOX", "stock", "3.20", "8.49", None, True, False, True, True, True),
    ("SKU-GRV-007", "Roasted Almonds 250g", ("Grocery", "Snacks"), "PCS", "stock", "4.80", "12.99", "8901234000400", True, False, True, True, True),
    ("SKU-GRV-008", "Dark Chocolate 70% 100g", ("Grocery", "Snacks"), "PCS", "stock", "2.50", "6.49", None, True, False, True, True, True),
]

_DEMO_CATEGORIES = [
    ("Electronics", None),
    ("Phones", "Electronics"),
    ("Laptops", "Electronics"),
    ("Accessories", "Electronics"),
    ("Apparel", None),
    ("Home & Kitchen", None),
    ("Grocery", None),
    ("Services", None),
    ("Audio", "Electronics"),
    ("Wearables", "Electronics"),
    ("Cameras", "Electronics"),
    ("Tablets", "Electronics"),
    ("Sports & Outdoors", None),
    ("Fitness", "Sports & Outdoors"),
    ("Cycling", "Sports & Outdoors"),
    ("Beauty & Personal Care", None),
    ("Skincare", "Beauty & Personal Care"),
    ("Toys & Games", None),
    ("Stationery", None),
    ("Beverages", "Grocery"),
    ("Snacks", "Grocery"),
]

#: Demo prices were authored in USD; the store trades in INR, so scale them.
_DEMO_USD_TO_INR = Decimal("85")


def _to_inr(amount: str) -> str:
    """Convert a demo USD price into a realistic INR amount."""
    return str((Decimal(amount) * _DEMO_USD_TO_INR).quantize(Decimal("0.01")))


#: (pincode, eta_days, cod_allowed) — demo delivery zones across India.
_DEMO_ZONES = [
    # Karnataka
    ("560001", 2, True),
    ("560002", 2, True),
    ("560034", 2, True),
    ("560103", 3, True),
    # Delhi NCR
    ("110001", 3, True),
    ("110016", 4, False),
    ("122001", 3, True),
    ("201301", 3, True),
    # Maharashtra
    ("400001", 3, True),
    ("400051", 3, True),
    ("411001", 3, True),
    ("440001", 4, True),
    # South
    ("600001", 4, True),
    ("600042", 4, True),
    ("500001", 3, True),
    ("500081", 3, False),
    ("641001", 4, True),
    ("682001", 5, True),
    ("695001", 5, True),
    ("570001", 4, True),
    # West & Central
    ("700001", 5, True),
    ("380001", 3, True),
    ("302001", 4, True),
    ("462001", 5, True),
    ("492001", 5, False),
    ("403001", 5, False),
    # North & East
    ("226001", 4, True),
    ("208001", 4, True),
    ("160017", 4, True),
    ("248001", 5, True),
    ("751001", 6, False),
    ("800001", 6, False),
    ("834001", 6, False),
    ("781001", 6, False),
]


#: (prefix, eta_days, cod_allowed) — state-wide coverage. The first two digits
#: of an Indian PIN identify its postal circle, so one row per circle covers the
#: whole state; exact city PINs above override these with faster ETAs.
_DEMO_ZONE_PREFIXES = [
    ("11", 4, True),   # Delhi
    ("12", 4, True),   # Haryana
    ("13", 5, True),
    ("14", 5, True),   # Punjab
    ("15", 5, True),
    ("16", 5, True),
    ("17", 6, False),  # Himachal Pradesh
    ("18", 7, False),  # Jammu & Kashmir
    ("19", 8, False),  # Ladakh
    ("20", 6, True),   # Uttar Pradesh / Uttarakhand
    ("21", 6, True),
    ("22", 6, True),
    ("23", 6, True),
    ("24", 6, True),
    ("25", 6, True),
    ("26", 6, True),
    ("27", 6, True),
    ("28", 6, True),
    ("30", 5, True),   # Rajasthan
    ("31", 5, True),
    ("32", 5, True),
    ("33", 6, True),
    ("34", 6, True),
    ("36", 5, True),   # Gujarat
    ("37", 5, True),
    ("38", 4, True),
    ("39", 6, False),
    ("40", 3, True),   # Maharashtra (Mumbai / Konkan)
    ("41", 3, True),   # Pune
    ("42", 4, True),
    ("43", 5, True),
    ("44", 4, True),
    ("45", 6, True),   # Madhya Pradesh
    ("46", 6, True),
    ("47", 6, True),
    ("48", 6, True),
    ("49", 6, False),  # Chhattisgarh
    ("50", 4, True),   # Telangana
    ("51", 5, True),   # Andhra Pradesh
    ("52", 5, True),
    ("53", 5, True),
    ("56", 3, True),   # Karnataka
    ("57", 4, True),
    ("58", 5, True),
    ("59", 5, True),
    ("60", 4, True),   # Tamil Nadu
    ("61", 5, True),
    ("62", 5, True),
    ("63", 5, True),
    ("64", 5, True),
    ("67", 5, True),   # Kerala
    ("68", 5, True),
    ("69", 5, True),
    ("70", 4, True),   # West Bengal
    ("71", 5, True),
    ("72", 5, True),
    ("73", 6, False),
    ("74", 6, False),
    ("75", 6, False),  # Odisha
    ("76", 6, False),
    ("77", 6, False),
    ("78", 7, False),  # Assam
    ("79", 7, False),  # North East
    ("80", 6, True),   # Bihar
    ("81", 6, True),
    ("82", 6, True),
    ("83", 6, True),   # Jharkhand
    ("84", 6, True),
    ("85", 6, True),
]


#: Demo pricing uses the Indian GST slabs; 18% is what the storefront charges by default.
_GST_SLABS = [(5, "GST5", "GST 5%"), (12, "GST12", "GST 12%"), (18, "GST18", "GST 18%")]


def _seed_taxes(session, company, admin) -> None:
    """Give the demo company real GST slabs (5 / 12 / 18, 18% default).

    The original demo seed created one fake "Sales VAT 10%" rate; it is retired
    here so carts, orders and invoices show a proper GST slab. Demo defaults are
    authoritative: 18% is the single default for sales and purchases.
    """
    from sqlalchemy import select

    from app.modules.taxes.models import TaxRate

    rows = list(
        session.execute(select(TaxRate).where(TaxRate.company_id == company.id)).scalars()
    )
    for row in rows:
        if row.code == "VAT10" or row.name == "Sales VAT 10%":
            session.delete(row)
    session.flush()

    existing = {row.code: row for row in rows if row.code != "VAT10"}
    for percentage, code, name in _GST_SLABS:
        rate = existing.get(code)
        if rate is None:
            rate = TaxRate(company_id=company.id, code=code, name=name, created_by=admin.id)
            session.add(rate)
        rate.name = name
        rate.percentage = percentage
        rate.is_active = True
    session.flush()

    for rate in session.execute(
        select(TaxRate).where(TaxRate.company_id == company.id)
    ).scalars():
        rate.is_default_sales = rate.code == "GST18"
        rate.is_default_purchase = rate.code == "GST18"
    session.flush()


def _seed_storefront_zones(session, company, admin) -> None:
    """Delivery coverage: state-wide prefixes plus exact city PINs (faster ETA,
    COD policy) so any valid Indian PIN resolves."""
    from app.modules.storefront import service as storefront

    for prefix, eta_days, cod_allowed in _DEMO_ZONE_PREFIXES:
        storefront.set_delivery_zone(
            session,
            company.id,
            pincode=prefix,
            deliverable=True,
            eta_days=eta_days,
            cod_allowed=cod_allowed,
        )

    for pincode, eta_days, cod_allowed in _DEMO_ZONES:
        storefront.set_delivery_zone(
            session,
            company.id,
            pincode=pincode,
            deliverable=True,
            eta_days=eta_days,
            cod_allowed=cod_allowed,
        )


def _seed_demo_catalog(session, company, admin) -> None:
    """Categories, UoMs and a wide product range spanning every filter axis:
    category, stock type, batch/serial tracking, active and sellable flags."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.modules.catalog.models import Product

    # categories (parent/child) — idempotent by name
    existing = {c.name: c for c in catalog.list_categories(session, company.id)}
    for name, parent in _DEMO_CATEGORIES:
        if name in existing:
            continue
        created = catalog.create_category(
            session, company_id=company.id, name=name,
            parent_id=existing[parent].id if parent else None,
        )
        existing[name] = created
    category_id = {name: row.id for name, row in existing.items()}

    uom_id: dict[str, str] = {}
    for code, name in [("PCS", "Piece"), ("BOX", "Box"), ("KG", "Kilogram"), ("HR", "Hour"), ("BAG", "Bag")]:
        uom_id[code] = catalog.ensure_uom(session, company_id=company.id, code=code, name=name).id

    skus = {
        sku
        for (sku,) in session.execute(
            select(Product.sku).where(Product.company_id == company.id)
        ).all()
    }
    created = 0
    for (
        sku, name, cat_path, uom, stock_type, cost, price, barcode, batches, serials, active, sellable, purchasable
    ) in _DEMO_PRODUCTS:
        if sku in skus:
            continue
        catalog.create_product(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            data={
                "sku": sku,
                "name": name,
                "category_id": category_id[cat_path[-1]],
                "uom_id": uom_id.get(uom),
                "barcode": barcode,
                "hsn_sac": _HSN_BY_CATEGORY.get(cat_path[-1]),
                "stock_type": stock_type,
                "track_batches": batches,
                "track_serials": serials,
                "base_cost": _to_inr(cost),
                "base_price": _to_inr(price),
                "is_active": active,
                "is_sellable": sellable,
                "is_purchasable": purchasable,
            },
        )
        created += 1
    if created:
        logger.info("seeded %d demo products", created)

    # top up HSN/SAC codes on demo products seeded before the field existed
    hsn_by_sku = {sku: _HSN_BY_CATEGORY.get(cat_path[-1]) for sku, _n, cat_path, *_ in _DEMO_PRODUCTS}
    coded = 0
    for product in session.execute(
        select(Product).where(Product.company_id == company.id)
    ).scalars():
        hsn = hsn_by_sku.get(product.sku)
        if hsn and not product.hsn_sac:
            product.hsn_sac = hsn
            coded += 1
    if coded:
        session.flush()
        logger.info("set HSN/SAC on %d demo products", coded)


_DEMO_PARTNER_CUSTOMERS = [
    # (code, name, email, phone, payment_term_days, credit_limit)
    ("C-001", "Demo Customer", "customer@example.com", "+1 555 0100", 0, "0"),
    ("C-002", "Alpha Traders", "orders@alphatraders.example.com", "+1 555 0101", 15, "5000"),
    ("C-003", "Beta Retail Group", "ap@betaretail.example.com", "+1 555 0102", 30, "10000"),
    ("C-004", "Globex Imports", "buying@globex.example.com", "+1 555 0103", 30, "15000"),
    ("C-005", "Harbor Stores", "hello@harborstores.example.com", "+1 555 0104", 0, "2500"),
    ("C-006", "Iris Boutique", "style@irisboutique.example.com", "+1 555 0105", 15, "3000"),
    ("C-007", "Junction Mart", "orders@junctionmart.example.com", "+1 555 0106", 45, "12000"),
    ("C-008", "Keystone Wholesale", "accounts@keystonewholesale.example.com", "+1 555 0107", 60, "25000"),
    ("C-009", "Luminary Gifts", "gifts@luminary.example.com", "+1 555 0108", 0, "1500"),
]

#: Business buyers carry a GSTIN, so their printed invoices show a registered buyer.
_DEMO_B2B_CUSTOMERS = [
    # (code, name, email, phone, payment_term_days, credit_limit, GSTIN)
    ("C-010", "Acme Traders Pvt Ltd", "accounts@acmetraders.example.com", "+91 80 4000 1234", 30, "50000", "29AABCA1234B1Z6"),
]

_DEMO_PARTNER_VENDORS = [
    # (code, name, email, phone)
    ("V-001", "Demo Vendor", "vendor@example.com", "+1 555 0200"),
    ("V-002", "Northwind Components", "sales@northwind.example.com", "+1 555 0201"),
    ("V-003", "Pacific Textiles", "sales@pacifictextiles.example.com", "+1 555 0202"),
    ("V-004", "Harvest Foods Wholesale", "orders@harvestfoods.example.com", "+1 555 0203"),
]


def _seed_demo_partners(session, company, admin) -> None:
    """Customers and vendors across varied payment terms and credit limits —
    guarded by their natural key (code)."""
    from sqlalchemy import select

    from app.modules.partners.models import Customer, Vendor

    cust_codes = set(
        session.scalars(select(Customer.code).where(Customer.company_id == company.id)).all()
    )
    created = 0
    for code, name, email, phone, terms, credit in _DEMO_PARTNER_CUSTOMERS:
        if code in cust_codes:
            continue
        partners.create_customer(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            data={
                "code": code,
                "name": name,
                "email": email,
                "phone": phone,
                "payment_term_days": terms,
                "credit_limit": credit,
            },
        )
        created += 1

    for code, name, email, phone, terms, credit, gstin in _DEMO_B2B_CUSTOMERS:
        if code in cust_codes:
            continue
        partners.create_customer(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            data={
                "code": code,
                "name": name,
                "email": email,
                "phone": phone,
                "payment_term_days": terms,
                "credit_limit": credit,
                "tax_identifier": gstin,
                "notes": "Demo B2B account (GST registered)",
            },
        )
        created += 1

    vend_codes = set(
        session.scalars(select(Vendor.code).where(Vendor.company_id == company.id)).all()
    )
    for code, name, email, phone in _DEMO_PARTNER_VENDORS:
        if code in vend_codes:
            continue
        partners.create_vendor(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            data={"code": code, "name": name, "email": email, "phone": phone},
        )
        created += 1
    if created:
        logger.info("seeded %d demo customers/vendors", created)


def _seed_demo_stock(session, company, admin, bin_location) -> None:
    """Opening stock into the demo bin. Batch products carry a batch ref and
    expiry date, serial products one serial per unit. Guarded per-SKU by the
    seed ledger entries (source_type='seed', source_id='seed:<sku>')."""
    from sqlalchemy import select

    from app.modules.catalog.models import Product
    from app.modules.inventory import service as inventory
    from app.modules.inventory.models import StockLedgerEntry

    if bin_location is None:
        logger.warning("no bin location available — skipping demo stock")
        return

    products = {
        p.sku: p
        for p in session.execute(select(Product).where(Product.company_id == company.id)).scalars()
    }
    today = date.today()
    received = 0
    for (
        sku, _name, _cat, _uom, stock_type, _cost, _price, _barcode, batches, serials, *_rest
    ) in _DEMO_PRODUCTS:
        if stock_type != "stock":
            continue
        product = products.get(sku)
        if product is None:
            continue
        already = session.scalar(
            select(StockLedgerEntry.id).where(
                StockLedgerEntry.company_id == company.id,
                StockLedgerEntry.source_type == "seed",
                StockLedgerEntry.source_id == f"seed:{sku}",
            )
        )
        if already:
            continue
        if serials:
            qty = 10
            serial_list = [f"{sku}-SN{i:04d}" for i in range(1, qty + 1)]
        else:
            # deterministic spread 60..360 in steps of 50, stable per SKU
            qty = 60 + (sum(ord(c) for c in sku) % 7) * 50
            serial_list = None
        inventory.post_movement(
            session,
            company_id=company.id,
            movement_type="receipt",
            product_id=product.id,
            location_id=bin_location.id,
            quantity=qty,
            unit_cost=product.base_cost,
            batch_ref=f"{sku}-B01" if batches else None,
            expiry_date=(today + timedelta(days=540)) if batches else None,
            serials=serial_list,
            source_type="seed",
            source_id=f"seed:{sku}",
            actor_user_id=admin.id,
        )
        received += 1
    if received:
        logger.info("received opening stock for %d products", received)


# Each spec drives the real service path (cart -> checkout -> pay ->
# shipment transitions). Orders are marked with notes "DEMO-ORDER nn" so
# re-runs skip them; backdate is clamped to the fiscal year start.
_DEMO_ORDERS = [
    # pending payment (stock reserved, nothing shipped)
    dict(customer="C-002", lines=[("SKU-PHX-001", 2), ("SKU-ACC-001", 2)], shipping="4.99", backdate=1),
    dict(customer="C-003", lines=[("SKU-APP-001", 3)], shipping="0", backdate=0),
    # paid, awaiting fulfillment
    dict(customer="C-004", lines=[("SKU-LAP-001", 1), ("SKU-ACC-002", 1)], shipping="12.00", backdate=6, pay=True),
    dict(customer="C-005", lines=[("SKU-001", 10), ("SKU-002", 4)], shipping="0", backdate=9, pay=True),
    # shipment progression
    dict(customer="C-006", lines=[("SKU-HOM-001", 2)], shipping="5.00", backdate=12, pay=True, ship="picking"),
    dict(customer="C-007", lines=[("SKU-GRV-001", 6), ("SKU-GRV-002", 4)], shipping="5.00", backdate=14, pay=True, ship="picked"),
    dict(customer="C-008", lines=[("SKU-ACC-004", 3), ("SKU-SVC-002", 1)], shipping="0", backdate=16, pay=True, ship="packed"),
    dict(customer="C-009", lines=[("SKU-APP-003", 2), ("SKU-APP-005", 2)], shipping="5.00", backdate=18, pay=True, ship="packed"),
    dict(customer="C-002", lines=[("SKU-HOM-002", 1)], shipping="5.00", backdate=20, pay=True, ship="dispatched"),
    dict(customer="C-003", lines=[("SKU-GRV-003", 5)], shipping="5.00", backdate=22, pay=True, ship="in_transit"),
    dict(customer="C-004", lines=[("SKU-LAP-002", 1), ("SKU-ACC-003", 2)], shipping="0", backdate=24, pay=True, ship="delivered"),
    dict(customer="C-001", lines=[("SKU-001", 5), ("SKU-SVC", 1)], shipping="0", backdate=26, pay=True, ship="delivered"),
    dict(customer="C-005", lines=[("SKU-HOM-003", 3), ("SKU-HOM-005", 1)], shipping="5.00", backdate=28, pay=True, ship="delivered"),
    # exception paths
    dict(customer="C-006", lines=[("SKU-APP-004", 1)], shipping="5.00", backdate=30, pay=True, ship="failed"),
    dict(customer="C-007", lines=[("SKU-GRV-004", 2)], shipping="5.00", backdate=33, pay=True, ship="returned_to_origin"),
    dict(customer="C-008", lines=[("SKU-ACC-005", 10)], shipping="0", backdate=2, cancel=True),
    # B2B buyer with a GSTIN — a delivered invoice shows a registered buyer
    dict(customer="C-010", lines=[("SKU-LAP-001", 2), ("SKU-ACC-001", 2)], shipping="5.00", backdate=4, pay=True, ship="delivered"),
]

# shipment status walk starting from 'picking' (create_shipment's initial state)
_SHIP_PATHS = {
    "picking": [],
    "picked": ["picked"],
    "packed": ["picked", "packed"],
    "dispatched": ["picked", "packed", "dispatched"],
    "in_transit": ["picked", "packed", "dispatched", "in_transit"],
    "delivered": ["picked", "packed", "dispatched", "in_transit", "delivered"],
    "failed": ["picked", "packed", "dispatched", "in_transit", "failed"],
    "returned_to_origin": ["picked", "packed", "dispatched", "in_transit", "failed", "returned_to_origin"],
}


def _seed_demo_orders(session, company, admin, *, floor_date: date) -> None:
    """Orders across every reachable status, via the real sales/fulfillment
    services so reservations, invoices, stock issues and GL stay consistent."""
    from sqlalchemy import select

    from app.modules.catalog.models import Product
    from app.modules.fulfillment import service as fulfillment
    from app.modules.partners.models import Customer
    from app.modules.sales import service as sales
    from app.modules.sales.models import SalesOrder

    customers = {
        c.code: c
        for c in session.execute(select(Customer).where(Customer.company_id == company.id)).scalars()
    }
    products = {
        p.sku: p
        for p in session.execute(select(Product).where(Product.company_id == company.id)).scalars()
    }

    today = date.today()
    max_backdate = max(0, (today - floor_date).days - 1)
    created_count = 0
    for index, spec in enumerate(_DEMO_ORDERS, start=1):
        notes = f"DEMO-ORDER {index:02d}"
        exists = session.scalar(
            select(SalesOrder.id).where(
                SalesOrder.company_id == company.id, SalesOrder.notes == notes
            )
        )
        if exists:
            continue
        customer = customers.get(spec["customer"])
        if customer is None:
            logger.warning("customer %s missing; skipping %s", spec["customer"], notes)
            continue

        cart = sales.get_or_create_cart(
            session, company_id=company.id, user_id=admin.id, customer_id=customer.id, token=None
        )
        for item in sales.cart_items(session, cart.id):
            sales.remove_cart_item(session, cart, item.id)
        for sku, line_qty in spec["lines"]:
            product = products.get(sku)
            if product is None:
                raise RuntimeError(f"demo order {notes} references missing SKU {sku}")
            sales.add_cart_item(session, cart, product.id, str(line_qty))

        order, _replayed = sales.checkout_cart(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            cart_id=cart.id,
            customer_id=customer.id,
            shipping_address="221B Demo Street, Springfield",
            billing_address=None,
            shipping_total=spec["shipping"],
            notes=notes,
            idempotency_key=f"seed-order-{index:02d}",
        )
        # backdate before payment: the invoice date derives from order_date
        backdate = min(spec.get("backdate", 0), max_backdate)
        if backdate:
            order.order_date = today - timedelta(days=backdate)
            session.flush()

        if spec.get("cancel"):
            sales.cancel_order(session, order, admin.id)
            created_count += 1
            continue
        if not spec.get("pay"):
            created_count += 1
            continue

        sales.pay_order(
            session,
            company_id=company.id,
            actor_user_id=admin.id,
            order_id=order.id,
            idempotency_key=f"seed-pay-{index:02d}",
        )
        target = spec.get("ship")
        if target:
            shipment = fulfillment.create_shipment(
                session, company_id=company.id, actor_user_id=admin.id, order_id=order.id
            )
            for to_status in _SHIP_PATHS[target]:
                fulfillment.transition_shipment(
                    session, company.id, shipment.id, to_status, admin.id
                )
        created_count += 1
    if created_count:
        logger.info("seeded %d demo orders", created_count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
