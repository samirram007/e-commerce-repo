"""Public storefront seed data — the records that used to live in the
frontend's `demo-catalog.ts`, now owned by the backend.

Prices are decimal strings (money never uses floats). `image` names map to the
photos in `app/seed_assets/storefront/<kind>/`; the seed registers each as a
public StoredFile served by the media route. Attribution for the photos is in
`app/seed_assets/storefront/MANIFEST.md`.
"""

# (slug, name, blurb, tone)
CATEGORIES = [
    ("electronics", "Electronics", "Audio, wearables and smart gear", "indigo"),
    ("fashion", "Fashion", "Everyday wear and statement pieces", "rose"),
    ("home", "Home & Living", "Decor, kitchen and comfort", "amber"),
    ("beauty", "Beauty", "Skincare and self-care rituals", "violet"),
    ("sports", "Sports & Outdoors", "Gear for every adventure", "emerald"),
    ("accessories", "Accessories", "Bags, watches and finishing touches", "sky"),
]

#: Every product is priced in INR already (the store currency).
#:
#: (sku, name, category_slug, price, compare_at, rating, reviews, tone, badge,
#:  description, highlights, colors, stock)
PRODUCTS = [
    (
        "EL-1001", "Aurora Wireless Headphones", "electronics",
        "7999.00", "10999.00", "4.7", 1284, "indigo", "Bestseller",
        "Over-ear headphones with adaptive noise cancellation, 40-hour battery life and plush memory-foam cushions tuned for long listening sessions.",
        ["Adaptive ANC", "40h battery", "USB-C fast charge", "Multipoint Bluetooth 5.3"],
        ["#1f2937", "#e5e7eb", "#4f46e5"], 42,
    ),
    (
        "EL-1002", "Pulse Smartwatch S2", "electronics",
        "12499.00", None, "4.5", 812, "sky", "New",
        "AMOLED smartwatch with heart-rate, SpO2 and sleep tracking, built-in GPS and a week of battery on a single charge.",
        ['1.4" AMOLED', "Built-in GPS", "7-day battery", "5 ATM water resistant"],
        ["#111827", "#f59e0b", "#10b981"], 18,
    ),
    (
        "EL-1003", "Echo Mini Speaker", "electronics",
        "3499.00", "4499.00", "4.4", 530, "violet", "Sale",
        "Pocket-sized Bluetooth speaker with surprisingly deep bass, IP67 dust and water protection and 12 hours of playtime.",
        ["IP67 rated", "12h playtime", "Stereo pairing", "Built-in mic"],
        ["#7c3aed", "#0f172a", "#f43f5e"], 64,
    ),
    (
        "EL-1004", "Nova Pro Earbuds", "electronics",
        "5999.00", None, "4.6", 2210, "slate", None,
        "True wireless earbuds with spatial audio, a pocketable charging case and touch controls you can customise.",
        ["Spatial audio", "30h with case", "Wireless charging", "IPX5"],
        ["#f8fafc", "#1e293b"], 120,
    ),
    (
        "FA-2001", "Coastal Linen Shirt", "fashion",
        "1899.00", "2499.00", "4.3", 342, "rose", "Sale",
        "Breathable pure-linen shirt with a relaxed fit, mother-of-pearl buttons and a soft garment-washed finish.",
        ["100% linen", "Relaxed fit", "Garment washed", "Machine washable"],
        ["#f5f5f4", "#93c5fd", "#d6d3d1"], 75,
    ),
    (
        "FA-2002", "Heritage Denim Jacket", "fashion",
        "3999.00", None, "4.8", 618, "indigo", "Bestseller",
        "A timeless trucker jacket cut from heavyweight selvedge denim that ages beautifully with every wear.",
        ["Selvedge denim", "Copper rivets", "Two chest pockets", "Classic fit"],
        ["#1e3a8a", "#0f172a"], 26,
    ),
    (
        "FA-2003", "Cloudstep Runners", "fashion",
        "4599.00", None, "4.5", 954, "orange", "New",
        "Lightweight knit sneakers with a responsive foam sole that keeps you comfortable from morning commute to evening walk.",
        ["Breathable knit", "Responsive foam", "Recycled laces", "Removable insole"],
        ["#f97316", "#f8fafc", "#111827"], 33,
    ),
    (
        "FA-2004", "Merino Wool Scarf", "fashion",
        "1299.00", None, "4.2", 129, "amber", None,
        "Ultra-soft merino scarf in a generous length, woven to keep you warm without the itch.",
        ["Fine merino", "180cm length", "Fringed edges", "Gift boxed"],
        ["#b45309", "#78716c", "#1f2937"], 58,
    ),
    (
        "HO-3001", "Terra Ceramic Vase", "home",
        "1499.00", None, "4.6", 211, "amber", "Limited",
        "Hand-thrown stoneware vase with a speckled matte glaze. Every piece is slightly different.",
        ["Handmade", "Stoneware", "Watertight glaze", "28cm tall"],
        ["#d6d3d1", "#a16207"], 9,
    ),
    (
        "HO-3002", "Cloud Knit Throw", "home",
        "2799.00", "3499.00", "4.7", 488, "slate", "Sale",
        "Chunky knit throw blanket that drapes over the sofa and doubles as the coziest reading companion.",
        ["Chunky knit", "130 × 170cm", "Hypoallergenic", "Machine washable"],
        ["#e5e7eb", "#9ca3af", "#fde68a"], 40,
    ),
    (
        "HO-3003", "Brewline Pour-Over Set", "home",
        "2199.00", None, "4.5", 302, "orange", None,
        "Borosilicate glass carafe, stainless dripper and reusable filter — everything you need for a perfect morning cup.",
        ["600ml carafe", "Reusable filter", "Heat-proof glass", "Dishwasher safe"],
        ["#f8fafc", "#1f2937"], 52,
    ),
    (
        "HO-3004", "Arc LED Desk Lamp", "home",
        "3299.00", None, "4.4", 176, "sky", "New",
        "Dimmable LED desk lamp with a warm-to-cool colour range and a wireless charging base.",
        ["5 colour modes", "Wireless charger", "Touch dimmer", "Eye-care LED"],
        ["#111827", "#f8fafc"], 27,
    ),
    (
        "BE-4001", "Glow Vitamin C Serum", "beauty",
        "1199.00", None, "4.6", 1673, "orange", "Bestseller",
        "Brightening serum with 15% vitamin C and hyaluronic acid for an even, radiant complexion.",
        ["15% Vitamin C", "Hyaluronic acid", "Fragrance free", "30ml"],
        ["#fdba74"], 210,
    ),
    (
        "BE-4002", "Restore Night Cream", "beauty",
        "1599.00", "1999.00", "4.4", 421, "violet", "Sale",
        "Rich overnight cream with ceramides and peptides that restores the skin barrier while you sleep.",
        ["Ceramides", "Peptide complex", "Dermatologist tested", "50ml"],
        ["#ddd6fe"], 88,
    ),
    (
        "BE-4003", "Calm Bath Ritual Set", "beauty",
        "2499.00", None, "4.8", 96, "rose", "Limited",
        "A gift-ready set of lavender bath salts, body oil and a soy candle for a slow, restful evening.",
        ["Lavender blend", "Soy candle", "Gift box", "Vegan"],
        ["#fbcfe8", "#c4b5fd"], 14,
    ),
    (
        "BE-4004", "Velvet Lip Trio", "beauty",
        "899.00", None, "4.3", 638, "rose", None,
        "Three long-wear matte lip colours that feel weightless and stay put all day.",
        ["Matte finish", "12h wear", "Cruelty free", "3 × 3.5g"],
        ["#be123c", "#9d174d", "#f43f5e"], 140,
    ),
    (
        "SP-5001", "Grip Pro Yoga Mat", "sports",
        "2299.00", None, "4.7", 912, "emerald", "Bestseller",
        "Non-slip natural rubber mat with alignment guides and a carry strap.",
        ["6mm cushioning", "Natural rubber", "Alignment lines", "Carry strap"],
        ["#10b981", "#6366f1", "#1f2937"], 61,
    ),
    (
        "SP-5002", "Summit 28L Backpack", "sports",
        "4299.00", "5299.00", "4.6", 374, "slate", "Sale",
        "Weather-resistant daypack with a ventilated back panel, hydration sleeve and plenty of organised pockets.",
        ["28 litres", "Rain cover", "Hydration sleeve", "Laptop pocket"],
        ["#334155", "#15803d", "#ea580c"], 22,
    ),
    (
        "SP-5003", "Thermo Steel Bottle", "sports",
        "999.00", None, "4.5", 1503, "sky", None,
        "Double-wall insulated bottle that keeps drinks cold for 24 hours or hot for 12.",
        ["750ml", "24h cold / 12h hot", "Leak-proof lid", "BPA free"],
        ["#0ea5e9", "#f8fafc", "#111827"], 300,
    ),
    (
        "SP-5004", "Flex Resistance Bands", "sports",
        "799.00", None, "4.2", 488, "emerald", "New",
        "Set of five fabric resistance bands with progressive tension levels for home workouts.",
        ["5 levels", "Non-slip fabric", "Travel pouch", "Workout guide"],
        ["#22c55e", "#f59e0b"], 95,
    ),
    (
        "AC-6001", "Atelier Leather Tote", "accessories",
        "5499.00", None, "4.8", 267, "amber", "Limited",
        'Full-grain leather tote with a structured base, inner zip pocket and space for a 14" laptop.',
        ['Full-grain leather', 'Fits 14" laptop', "Zip pocket", "Lifetime stitching warranty"],
        ["#92400e", "#1c1917"], 11,
    ),
    (
        "AC-6002", "Meridian Minimal Watch", "accessories",
        "6999.00", "8499.00", "4.6", 419, "slate", "Sale",
        "Slim 38mm watch with sapphire glass, Japanese quartz movement and an interchangeable strap.",
        ["Sapphire crystal", "Japanese quartz", "5 ATM", "Quick-release strap"],
        ["#e5e7eb", "#d4a373", "#111827"], 30,
    ),
    (
        "AC-6003", "Horizon Polarised Sunglasses", "accessories",
        "2499.00", None, "4.4", 588, "sky", "New",
        "Lightweight acetate frames with polarised UV400 lenses and a scratch-resistant coating.",
        ["Polarised", "UV400", "Acetate frame", "Hard case included"],
        ["#1f2937", "#b45309"], 47,
    ),
    (
        "AC-6004", "Slim Card Wallet", "accessories",
        "1099.00", None, "4.5", 802, "indigo", None,
        "RFID-blocking minimalist wallet that holds up to eight cards and a few folded notes.",
        ["RFID blocking", "Holds 8 cards", "Vegetable-tanned leather", "Pull tab"],
        ["#1e3a8a", "#78350f", "#111827"], 160,
    ),
]

#: (eyebrow, title, text, cta, category_slug, tone, image)
HERO_SLIDES = [
    (
        "New season", "Sound that moves with you",
        "Wireless audio and smart wearables, now up to 30% off for a limited time.",
        "Shop electronics", "electronics", "indigo", "electronics.jpg",
    ),
    (
        "Fresh drop", "Wear the weekend",
        "Linen, denim and light layers built for long days and warm evenings.",
        "Explore fashion", "fashion", "rose", "fashion.jpg",
    ),
    (
        "Make it home", "Slow mornings, softer evenings",
        "Handmade ceramics, cozy throws and everything for your favourite corner.",
        "Shop home", "home", "amber", "home.jpg",
    ),
    (
        "Move more", "Gear up for every trail",
        "Backpacks, bottles and training essentials — free shipping on all sports orders.",
        "Shop sports", "sports", "emerald", "sports.jpg",
    ),
]

#: (name, city, quote)
TESTIMONIALS = [
    ("Ananya R.", "Bengaluru", "Ordered the Aurora headphones on a Monday, had them Wednesday. Packaging was lovely and the sound is unreal."),
    ("Rahul M.", "Pune", "The denim jacket fits perfectly. Exchange for a different size took two days — no questions asked."),
    ("Sneha K.", "Delhi", "My go-to for gifts. The bath ritual set was a hit and it arrived beautifully wrapped."),
    ("Arjun P.", "Chennai", "Great prices on everyday stuff and the deals actually feel like deals. Checkout is quick too."),
    ("Meera S.", "Mumbai", "Customer support sorted a delayed delivery in minutes. Rare to see that kind of care."),
]

#: (group, question, answer)
FAQS = [
    ("Orders & payment", "Which payment methods do you accept?", "UPI, all major credit and debit cards, net banking and cash on delivery for eligible pincodes."),
    ("Orders & payment", "Can I change or cancel my order?", "You can cancel any order before it is shipped from your order page. Once shipped, you can request a return after delivery."),
    ("Orders & payment", "Do I need an account to order?", "No — guest checkout is available. Creating an account lets you track orders and keep a wishlist across devices."),
    ("Shipping", "How long does delivery take?", "Metro cities usually receive orders in 2–3 business days and other locations in 4–7 business days."),
    ("Shipping", "Is shipping free?", "Shipping is free on orders above ₹999. A flat ₹79 fee applies to smaller orders."),
    ("Shipping", "Do you ship internationally?", "We currently ship within India only. International shipping is on our roadmap."),
    ("Returns & refunds", "What is your return policy?", "Most items can be returned within 15 days of delivery in their original condition. Beauty products must be unopened."),
    ("Returns & refunds", "When will I get my refund?", "Refunds are issued to the original payment method within 5–7 business days after we receive the return."),
]

#: (slug, title, updated, sections)
POLICIES = [
    (
        "shipping", "Shipping Policy", "October 2026",
        [
            {"heading": "Delivery timelines", "body": "Orders are dispatched within 24 hours on business days. Metro cities receive deliveries in 2–3 business days; other serviceable pincodes in 4–7 business days."},
            {"heading": "Shipping charges", "body": "Shipping is free on orders above ₹999. Orders below that carry a flat ₹79 shipping fee, shown at checkout before you pay."},
            {"heading": "Tracking", "body": "As soon as your order ships you will receive an email with a tracking link. You can also see live status on your orders page."},
        ],
    ),
    (
        "returns", "Returns & Refunds", "October 2026",
        [
            {"heading": "Return window", "body": "You can return most products within 15 days of delivery, provided they are unused and in original packaging with tags attached."},
            {"heading": "Non-returnable items", "body": "Opened beauty and personal-care products, gift cards and items marked final sale cannot be returned for hygiene and safety reasons."},
            {"heading": "Refunds", "body": "Once your return passes inspection, the refund is issued to your original payment method within 5–7 business days. Cash-on-delivery orders are refunded by bank transfer."},
        ],
    ),
    (
        "privacy", "Privacy Policy", "October 2026",
        [
            {"heading": "What we collect", "body": "We collect the details you give us at checkout — name, contact information and delivery address — along with basic browsing data that helps the store work, such as your cart."},
            {"heading": "How we use it", "body": "Your information is used to process orders, provide support and, only if you opt in, send offers. We never sell your personal data."},
            {"heading": "Your choices", "body": "You can request a copy of your data or ask us to delete it at any time by contacting support."},
        ],
    ),
    (
        "terms", "Terms of Service", "October 2026",
        [
            {"heading": "Using the store", "body": "By placing an order you confirm that the information you provide is accurate and that you are authorised to use the chosen payment method."},
            {"heading": "Pricing", "body": "Prices include applicable taxes unless stated otherwise. In the rare case of a pricing error we will contact you before shipping and you may cancel for a full refund."},
            {"heading": "Liability", "body": "Our liability for any order is limited to the amount paid for that order, to the extent permitted by law."},
        ],
    ),
]

#: Store settings: shipping rules, contact block (map image from
#: `contact/map.jpg`) and the marketing copy lists the shop chrome renders.
SETTINGS = {
    "free_shipping_threshold": "999",
    "flat_shipping_fee": "79",
    "contact_phone": "+91 80 4000 1234",
    "contact_email": "hello@shopora.example",
    "contact_address": "42 Market Street, Bengaluru 560001",
    "map_image": "map.jpg",
    "announcements": [
        "Free shipping on orders above ₹999",
        "Easy 15-day returns",
        "Festive sale — up to 30% off electronics",
        "Cash on delivery available",
        "New arrivals every Friday",
    ],
    "perks": [
        {"icon": "truck", "title": "Free shipping", "text": "On every order above ₹999"},
        {"icon": "rotate-ccw", "title": "15-day returns", "text": "No-fuss exchanges & refunds"},
        {"icon": "shield-check", "title": "Secure payments", "text": "UPI, cards & cash on delivery"},
        {"icon": "headphones", "title": "Real humans", "text": "Support 7 days a week"},
    ],
    "about_values": [
        {"icon": "award", "title": "Quality first", "text": "Every product is tested by our team before it earns a spot in the store."},
        {"icon": "leaf", "title": "Responsibly made", "text": "We favour makers using recycled materials and plastic-free packaging."},
        {"icon": "users", "title": "People-powered", "text": "A small team obsessed with making online shopping feel personal again."},
    ],
    "about_stats": [
        {"value": "250k+", "label": "Happy customers"},
        {"value": "19k", "label": "Pincodes served"},
        {"value": "4.7★", "label": "Average rating"},
        {"value": "48h", "label": "Average delivery"},
    ],
    "footer_about": "Thoughtfully chosen everyday essentials, delivered across India.",
}

#: Opening stock per SKU (units to receive into the demo bin).
STOCK = {product[0]: product[-1] for product in PRODUCTS}

#: Cover photo per SKU (files in `seed_assets/storefront/products/`).
PRODUCT_IMAGES = {
    "EL-1001": "p-aurora-headphones.jpg",
    "EL-1002": "p-pulse-watch.jpg",
    "EL-1003": "p-echo-speaker.jpg",
    "EL-1004": "p-nova-earbuds.jpg",
    "FA-2001": "p-linen-shirt.jpg",
    "FA-2002": "p-denim-jacket.jpg",
    "FA-2003": "p-runner-sneakers.jpg",
    "FA-2004": "p-wool-scarf.jpg",
    "HO-3001": "p-ceramic-vase.jpg",
    "HO-3002": "p-throw-blanket.jpg",
    "HO-3003": "p-pour-over.jpg",
    "HO-3004": "p-desk-lamp.jpg",
    "BE-4001": "p-glow-serum.jpg",
    "BE-4002": "p-night-cream.jpg",
    "BE-4003": "p-bath-set.jpg",
    "BE-4004": "p-lip-trio.jpg",
    "SP-5001": "p-yoga-mat.jpg",
    "SP-5002": "p-trail-backpack.jpg",
    "SP-5003": "p-steel-bottle.jpg",
    "SP-5004": "p-resistance-bands.jpg",
    "AC-6001": "p-leather-tote.jpg",
    "AC-6002": "p-minimal-watch.jpg",
    "AC-6003": "p-sunglasses.jpg",
    "AC-6004": "p-card-wallet.jpg",
}

#: Cost basis for seeded storefront products (they ship with no cost data of
#: their own); drives inventory valuation until real purchase costs arrive.
COST_RATIO = "0.5"

import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

logger = logging.getLogger("erp.seed.storefront")

_ASSET_ROOT = Path(__file__).resolve().parent.parent / "seed_assets" / "storefront"

_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _import_image(session, company_id, actor_user_id, *, kind, filename, purpose):
    """Register a seed photo as a public StoredFile (idempotent).

    Idempotency is by (purpose, original_name) scoped to the company: if a
    public file with this purpose + name already exists, it is reused instead of
    copied again.
    """
    from io import BytesIO

    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from app.shared.files import StoredFile, save_file

    existing = session.scalar(
        select(StoredFile).where(
            StoredFile.company_id == company_id,
            StoredFile.purpose == purpose,
            StoredFile.original_name == filename,
            StoredFile.visibility == "public",
        )
    )
    if existing is not None:
        return existing
    path = _ASSET_ROOT / kind / filename
    if not path.is_file():
        logger.warning("seed asset missing: %s", path)
        return None
    content_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    upload = UploadFile(
        file=BytesIO(path.read_bytes()),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )
    return save_file(
        session,
        upload,
        company_id=company_id,
        purpose=purpose,
        created_by=actor_user_id,
        allowed_types=_IMAGE_TYPES,
        visibility="public",
    )


def _as_decimal(value) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def seed_storefront(session, company, admin) -> None:
    """Upsert the public storefront content: categories (with images),
    storefront products (with gallery images and opening stock), hero slides,
    testimonials, FAQs, policies and store settings.

    Idempotent: categories by slug, products by SKU, content rows by their own
    natural keys, files by (purpose, original name).
    """
    from app.modules.catalog.models import Category, Product, ProductImage
    from app.modules.inventory import service as inventory
    from app.modules.inventory.models import StockLedgerEntry
    from app.modules.storage.models import StorageLocation
    from app.modules.storefront import service as svc
    from app.modules.storefront.models import (
        StorefrontFaq,
        StorefrontHeroSlide,
        StorefrontPolicy,
        StorefrontSettings,
        StorefrontTestimonial,
    )

    cid = company.id

    # ---- categories ----
    all_cats = session.execute(
        select(Category).where(Category.company_id == cid)
    ).scalars().all()
    existing_cats = {c.slug: c for c in all_cats if c.slug}
    by_name: dict[str, Category] = {}
    for c in all_cats:
        # adopt a same-named ERP category rather than duplicating it
        if c.name not in by_name or (by_name[c.name].slug and not c.slug):
            by_name[c.name] = c
    for position, (slug, name, blurb, tone) in enumerate(CATEGORIES):
        row = existing_cats.get(slug) or by_name.get(name)
        if row is None:
            row = Category(company_id=cid, name=name, slug=slug, created_by=admin.id)
            session.add(row)
        row.slug = row.slug or slug
        row.blurb = blurb
        row.tone = tone
        row.sort_order = position
        row.is_active = True
        session.flush()
        record = _import_image(
            session, cid, admin.id, kind="categories", filename=f"{slug}.jpg", purpose="category_image"
        )
        if record is not None:
            row.image_file_id = record.id
        existing_cats[slug] = row
    session.flush()

    # ---- products (+ gallery, opening stock) ----
    bin_location = next(
        (loc for loc in session.execute(
            select(StorageLocation).where(StorageLocation.company_id == cid)
        ).scalars() if loc.location_type == "bin"),
        None,
    )
    existing_products = {
        p.sku: p
        for p in session.execute(select(Product).where(Product.company_id == cid)).scalars()
    }
    for (
        sku, name, category_slug, price, compare_at, rating, reviews, tone, badge,
        description, highlights, colors, stock,
    ) in PRODUCTS:
        product = existing_products.get(sku)
        if product is None:
            product = Product(company_id=cid, sku=sku, name=name, created_by=admin.id)
            session.add(product)
        product.category_id = existing_cats[category_slug].id
        product.description = description
        product.stock_type = "stock"
        product.base_price = Decimal(price)
        product.base_cost = Decimal(price) * Decimal(COST_RATIO)
        product.is_active = True
        product.is_sellable = True
        product.is_purchasable = True
        product.compare_at_price = _as_decimal(compare_at)
        product.badge = badge
        product.highlights = list(highlights)
        product.colors = list(colors)
        product.rating_avg = _as_decimal(rating)
        product.rating_count = reviews
        product.tone = tone
        product.slug = f"{sku.lower()}-{name.lower().replace(' ', '-').replace('/', '-')[:40].strip('-')}"
        session.flush()
        # cover/gallery image
        record = _import_image(
            session, cid, admin.id, kind="products",
            filename=PRODUCT_IMAGES.get(sku, f"{sku.lower()}.jpg"), purpose="product_image"
        )
        if record is not None:
            product.image_file_id = record.id
            has_row = session.scalar(
                select(ProductImage.id).where(
                    ProductImage.product_id == product.id, ProductImage.file_id == record.id
                )
            )
            if has_row is None:
                session.add(ProductImage(
                    company_id=cid, product_id=product.id, file_id=record.id,
                    sort_order=0, alt=name, created_by=admin.id,
                ))
        session.flush()
        # opening stock through the inventory service (guarded by seed ledger)
        if bin_location is not None and stock:
            already = session.scalar(
                select(StockLedgerEntry.id).where(
                    StockLedgerEntry.company_id == cid,
                    StockLedgerEntry.source_type == "seed",
                    StockLedgerEntry.source_id == f"seed:{sku}",
                )
            )
            if already is None:
                inventory.post_movement(
                    session, company_id=cid, movement_type="receipt", product_id=product.id,
                    location_id=bin_location.id, quantity=Decimal(stock),
                    unit_cost=product.base_cost, source_type="seed", source_id=f"seed:{sku}",
                    actor_user_id=admin.id,
                )
        existing_products[sku] = product
    session.flush()

    # ---- hero slides ----
    existing_hero = {
        h.title: h
        for h in session.execute(
            select(StorefrontHeroSlide).where(StorefrontHeroSlide.company_id == cid)
        ).scalars()
    }
    for position, (eyebrow, title, text, cta, category_slug, tone, image) in enumerate(HERO_SLIDES):
        row = existing_hero.get(title)
        if row is None:
            row = StorefrontHeroSlide(company_id=cid, title=title, created_by=admin.id)
            session.add(row)
        row.eyebrow = eyebrow
        row.text = text
        row.cta = cta
        row.category_slug = category_slug
        row.tone = tone
        row.sort_order = position
        row.is_active = True
        session.flush()
        record = _import_image(
            session, cid, admin.id, kind="hero", filename=image, purpose="hero_image"
        )
        if record is not None:
            row.image_file_id = record.id
    session.flush()

    # ---- testimonials ----
    existing_quotes = {
        t.name: t
        for t in session.execute(
            select(StorefrontTestimonial).where(StorefrontTestimonial.company_id == cid)
        ).scalars()
    }
    for position, (name, city, quote) in enumerate(TESTIMONIALS):
        row = existing_quotes.get(name)
        if row is None:
            row = StorefrontTestimonial(company_id=cid, name=name, created_by=admin.id)
            session.add(row)
        row.city = city
        row.quote = quote
        row.sort_order = position
        row.is_active = True

    # ---- FAQs ----
    existing_faqs = {
        (f.group_name, f.question): f
        for f in session.execute(select(StorefrontFaq).where(StorefrontFaq.company_id == cid)).scalars()
    }
    for position, (group, question, answer) in enumerate(FAQS):
        row = existing_faqs.get((group, question))
        if row is None:
            row = StorefrontFaq(company_id=cid, group_name=group, question=question, created_by=admin.id)
            session.add(row)
        row.answer = answer
        row.sort_order = position
        row.is_active = True

    # ---- policies ----
    existing_policies = {
        p.slug: p
        for p in session.execute(select(StorefrontPolicy).where(StorefrontPolicy.company_id == cid)).scalars()
    }
    for position, (slug, title, updated, sections) in enumerate(POLICIES):
        row = existing_policies.get(slug)
        if row is None:
            row = StorefrontPolicy(company_id=cid, slug=slug, title=title, created_by=admin.id)
            session.add(row)
        row.title = title
        row.updated = updated
        row.sections = [dict(s) for s in sections]
        row.sort_order = position
        row.is_active = True
    session.flush()

    # ---- store settings ----
    settings = svc.get_settings_row(session, cid)
    if settings is None:
        settings = StorefrontSettings(company_id=cid, created_by=admin.id)
        session.add(settings)
    settings.free_shipping_threshold = Decimal(SETTINGS["free_shipping_threshold"])
    settings.flat_shipping_fee = Decimal(SETTINGS["flat_shipping_fee"])
    settings.contact_phone = SETTINGS["contact_phone"]
    settings.contact_email = SETTINGS["contact_email"]
    settings.contact_address = SETTINGS["contact_address"]
    settings.announcements = list(SETTINGS["announcements"])
    settings.perks = [dict(p) for p in SETTINGS["perks"]]
    settings.about_values = [dict(v) for v in SETTINGS["about_values"]]
    settings.about_stats = [dict(s) for s in SETTINGS["about_stats"]]
    settings.footer_about = SETTINGS["footer_about"]
    session.flush()
    record = _import_image(
        session, cid, admin.id, kind="contact", filename=SETTINGS["map_image"], purpose="contact_map"
    )
    if record is not None:
        settings.map_image_file_id = record.id
    session.flush()
    logger.info("storefront content upserted for company %s", cid)
