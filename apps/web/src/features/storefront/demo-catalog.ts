/**
 * Static showcase catalog for the public storefront pages.
 *
 * The backend does not expose public `/storefront/shop/*` endpoints yet, so the
 * marketing/browse pages render from this local catalog. Prices are decimal
 * strings, like every money value from the API. Images are intentionally left
 * as placeholders — each item carries a `tone` used to tint its placeholder.
 */

export type Tone = "indigo" | "rose" | "amber" | "emerald" | "sky" | "violet" | "slate" | "orange";

export interface DemoCategory {
  slug: string;
  name: string;
  blurb: string;
  tone: Tone;
}

export interface DemoProduct {
  id: string;
  sku: string;
  name: string;
  category: string;
  price: string;
  /** Pre-discount price; present only when the item is on sale. */
  compareAt?: string;
  rating: number;
  reviews: number;
  tone: Tone;
  badge?: "New" | "Sale" | "Bestseller" | "Limited";
  description: string;
  highlights: string[];
  colors: string[];
  stock: number;
}

export interface HeroSlide {
  eyebrow: string;
  title: string;
  text: string;
  cta: string;
  category?: string;
  tone: Tone;
}

export const CATEGORIES: DemoCategory[] = [
  { slug: "electronics", name: "Electronics", blurb: "Audio, wearables and smart gear", tone: "indigo" },
  { slug: "fashion", name: "Fashion", blurb: "Everyday wear and statement pieces", tone: "rose" },
  { slug: "home", name: "Home & Living", blurb: "Decor, kitchen and comfort", tone: "amber" },
  { slug: "beauty", name: "Beauty", blurb: "Skincare and self-care rituals", tone: "violet" },
  { slug: "sports", name: "Sports & Outdoors", blurb: "Gear for every adventure", tone: "emerald" },
  { slug: "accessories", name: "Accessories", blurb: "Bags, watches and finishing touches", tone: "sky" },
];

export const PRODUCTS: DemoProduct[] = [
  {
    id: "p-aurora-headphones", sku: "EL-1001", name: "Aurora Wireless Headphones", category: "electronics",
    price: "7999.00", compareAt: "10999.00", rating: 4.7, reviews: 1284, tone: "indigo", badge: "Bestseller",
    description: "Over-ear headphones with adaptive noise cancellation, 40-hour battery life and plush memory-foam cushions tuned for long listening sessions.",
    highlights: ["Adaptive ANC", "40h battery", "USB-C fast charge", "Multipoint Bluetooth 5.3"],
    colors: ["#1f2937", "#e5e7eb", "#4f46e5"], stock: 42,
  },
  {
    id: "p-pulse-watch", sku: "EL-1002", name: "Pulse Smartwatch S2", category: "electronics",
    price: "12499.00", rating: 4.5, reviews: 812, tone: "sky", badge: "New",
    description: "AMOLED smartwatch with heart-rate, SpO2 and sleep tracking, built-in GPS and a week of battery on a single charge.",
    highlights: ["1.4\" AMOLED", "Built-in GPS", "7-day battery", "5 ATM water resistant"],
    colors: ["#111827", "#f59e0b", "#10b981"], stock: 18,
  },
  {
    id: "p-echo-speaker", sku: "EL-1003", name: "Echo Mini Speaker", category: "electronics",
    price: "3499.00", compareAt: "4499.00", rating: 4.4, reviews: 530, tone: "violet", badge: "Sale",
    description: "Pocket-sized Bluetooth speaker with surprisingly deep bass, IP67 dust and water protection and 12 hours of playtime.",
    highlights: ["IP67 rated", "12h playtime", "Stereo pairing", "Built-in mic"],
    colors: ["#7c3aed", "#0f172a", "#f43f5e"], stock: 64,
  },
  {
    id: "p-nova-earbuds", sku: "EL-1004", name: "Nova Pro Earbuds", category: "electronics",
    price: "5999.00", rating: 4.6, reviews: 2210, tone: "slate",
    description: "True wireless earbuds with spatial audio, a pocketable charging case and touch controls you can customise.",
    highlights: ["Spatial audio", "30h with case", "Wireless charging", "IPX5"],
    colors: ["#f8fafc", "#1e293b"], stock: 120,
  },
  {
    id: "p-linen-shirt", sku: "FA-2001", name: "Coastal Linen Shirt", category: "fashion",
    price: "1899.00", compareAt: "2499.00", rating: 4.3, reviews: 342, tone: "rose", badge: "Sale",
    description: "Breathable pure-linen shirt with a relaxed fit, mother-of-pearl buttons and a soft garment-washed finish.",
    highlights: ["100% linen", "Relaxed fit", "Garment washed", "Machine washable"],
    colors: ["#f5f5f4", "#93c5fd", "#d6d3d1"], stock: 75,
  },
  {
    id: "p-denim-jacket", sku: "FA-2002", name: "Heritage Denim Jacket", category: "fashion",
    price: "3999.00", rating: 4.8, reviews: 618, tone: "indigo", badge: "Bestseller",
    description: "A timeless trucker jacket cut from heavyweight selvedge denim that ages beautifully with every wear.",
    highlights: ["Selvedge denim", "Copper rivets", "Two chest pockets", "Classic fit"],
    colors: ["#1e3a8a", "#0f172a"], stock: 26,
  },
  {
    id: "p-runner-sneakers", sku: "FA-2003", name: "Cloudstep Runners", category: "fashion",
    price: "4599.00", rating: 4.5, reviews: 954, tone: "orange", badge: "New",
    description: "Lightweight knit sneakers with a responsive foam sole that keeps you comfortable from morning commute to evening walk.",
    highlights: ["Breathable knit", "Responsive foam", "Recycled laces", "Removable insole"],
    colors: ["#f97316", "#f8fafc", "#111827"], stock: 33,
  },
  {
    id: "p-wool-scarf", sku: "FA-2004", name: "Merino Wool Scarf", category: "fashion",
    price: "1299.00", rating: 4.2, reviews: 129, tone: "amber",
    description: "Ultra-soft merino scarf in a generous length, woven to keep you warm without the itch.",
    highlights: ["Fine merino", "180cm length", "Fringed edges", "Gift boxed"],
    colors: ["#b45309", "#78716c", "#1f2937"], stock: 58,
  },
  {
    id: "p-ceramic-vase", sku: "HO-3001", name: "Terra Ceramic Vase", category: "home",
    price: "1499.00", rating: 4.6, reviews: 211, tone: "amber", badge: "Limited",
    description: "Hand-thrown stoneware vase with a speckled matte glaze. Every piece is slightly different.",
    highlights: ["Handmade", "Stoneware", "Watertight glaze", "28cm tall"],
    colors: ["#d6d3d1", "#a16207"], stock: 9,
  },
  {
    id: "p-throw-blanket", sku: "HO-3002", name: "Cloud Knit Throw", category: "home",
    price: "2799.00", compareAt: "3499.00", rating: 4.7, reviews: 488, tone: "slate", badge: "Sale",
    description: "Chunky knit throw blanket that drapes over the sofa and doubles as the coziest reading companion.",
    highlights: ["Chunky knit", "130 × 170cm", "Hypoallergenic", "Machine washable"],
    colors: ["#e5e7eb", "#9ca3af", "#fde68a"], stock: 40,
  },
  {
    id: "p-pour-over", sku: "HO-3003", name: "Brewline Pour-Over Set", category: "home",
    price: "2199.00", rating: 4.5, reviews: 302, tone: "orange",
    description: "Borosilicate glass carafe, stainless dripper and reusable filter — everything you need for a perfect morning cup.",
    highlights: ["600ml carafe", "Reusable filter", "Heat-proof glass", "Dishwasher safe"],
    colors: ["#f8fafc", "#1f2937"], stock: 52,
  },
  {
    id: "p-desk-lamp", sku: "HO-3004", name: "Arc LED Desk Lamp", category: "home",
    price: "3299.00", rating: 4.4, reviews: 176, tone: "sky", badge: "New",
    description: "Dimmable LED desk lamp with a warm-to-cool colour range and a wireless charging base.",
    highlights: ["5 colour modes", "Wireless charger", "Touch dimmer", "Eye-care LED"],
    colors: ["#111827", "#f8fafc"], stock: 27,
  },
  {
    id: "p-glow-serum", sku: "BE-4001", name: "Glow Vitamin C Serum", category: "beauty",
    price: "1199.00", rating: 4.6, reviews: 1673, tone: "orange", badge: "Bestseller",
    description: "Brightening serum with 15% vitamin C and hyaluronic acid for an even, radiant complexion.",
    highlights: ["15% Vitamin C", "Hyaluronic acid", "Fragrance free", "30ml"],
    colors: ["#fdba74"], stock: 210,
  },
  {
    id: "p-night-cream", sku: "BE-4002", name: "Restore Night Cream", category: "beauty",
    price: "1599.00", compareAt: "1999.00", rating: 4.4, reviews: 421, tone: "violet", badge: "Sale",
    description: "Rich overnight cream with ceramides and peptides that restores the skin barrier while you sleep.",
    highlights: ["Ceramides", "Peptide complex", "Dermatologist tested", "50ml"],
    colors: ["#ddd6fe"], stock: 88,
  },
  {
    id: "p-bath-set", sku: "BE-4003", name: "Calm Bath Ritual Set", category: "beauty",
    price: "2499.00", rating: 4.8, reviews: 96, tone: "rose", badge: "Limited",
    description: "A gift-ready set of lavender bath salts, body oil and a soy candle for a slow, restful evening.",
    highlights: ["Lavender blend", "Soy candle", "Gift box", "Vegan"],
    colors: ["#fbcfe8", "#c4b5fd"], stock: 14,
  },
  {
    id: "p-lip-trio", sku: "BE-4004", name: "Velvet Lip Trio", category: "beauty",
    price: "899.00", rating: 4.3, reviews: 638, tone: "rose",
    description: "Three long-wear matte lip colours that feel weightless and stay put all day.",
    highlights: ["Matte finish", "12h wear", "Cruelty free", "3 × 3.5g"],
    colors: ["#be123c", "#9d174d", "#f43f5e"], stock: 140,
  },
  {
    id: "p-yoga-mat", sku: "SP-5001", name: "Grip Pro Yoga Mat", category: "sports",
    price: "2299.00", rating: 4.7, reviews: 912, tone: "emerald", badge: "Bestseller",
    description: "Non-slip natural rubber mat with alignment guides and a carry strap.",
    highlights: ["6mm cushioning", "Natural rubber", "Alignment lines", "Carry strap"],
    colors: ["#10b981", "#6366f1", "#1f2937"], stock: 61,
  },
  {
    id: "p-trail-backpack", sku: "SP-5002", name: "Summit 28L Backpack", category: "sports",
    price: "4299.00", compareAt: "5299.00", rating: 4.6, reviews: 374, tone: "slate", badge: "Sale",
    description: "Weather-resistant daypack with a ventilated back panel, hydration sleeve and plenty of organised pockets.",
    highlights: ["28 litres", "Rain cover", "Hydration sleeve", "Laptop pocket"],
    colors: ["#334155", "#15803d", "#ea580c"], stock: 22,
  },
  {
    id: "p-steel-bottle", sku: "SP-5003", name: "Thermo Steel Bottle", category: "sports",
    price: "999.00", rating: 4.5, reviews: 1503, tone: "sky",
    description: "Double-wall insulated bottle that keeps drinks cold for 24 hours or hot for 12.",
    highlights: ["750ml", "24h cold / 12h hot", "Leak-proof lid", "BPA free"],
    colors: ["#0ea5e9", "#f8fafc", "#111827"], stock: 300,
  },
  {
    id: "p-resistance-bands", sku: "SP-5004", name: "Flex Resistance Bands", category: "sports",
    price: "799.00", rating: 4.2, reviews: 488, tone: "emerald", badge: "New",
    description: "Set of five fabric resistance bands with progressive tension levels for home workouts.",
    highlights: ["5 levels", "Non-slip fabric", "Travel pouch", "Workout guide"],
    colors: ["#22c55e", "#f59e0b"], stock: 95,
  },
  {
    id: "p-leather-tote", sku: "AC-6001", name: "Atelier Leather Tote", category: "accessories",
    price: "5499.00", rating: 4.8, reviews: 267, tone: "amber", badge: "Limited",
    description: "Full-grain leather tote with a structured base, inner zip pocket and space for a 14\" laptop.",
    highlights: ["Full-grain leather", "Fits 14\" laptop", "Zip pocket", "Lifetime stitching warranty"],
    colors: ["#92400e", "#1c1917"], stock: 11,
  },
  {
    id: "p-minimal-watch", sku: "AC-6002", name: "Meridian Minimal Watch", category: "accessories",
    price: "6999.00", compareAt: "8499.00", rating: 4.6, reviews: 419, tone: "slate", badge: "Sale",
    description: "Slim 38mm watch with sapphire glass, Japanese quartz movement and an interchangeable strap.",
    highlights: ["Sapphire crystal", "Japanese quartz", "5 ATM", "Quick-release strap"],
    colors: ["#e5e7eb", "#d4a373", "#111827"], stock: 30,
  },
  {
    id: "p-sunglasses", sku: "AC-6003", name: "Horizon Polarised Sunglasses", category: "accessories",
    price: "2499.00", rating: 4.4, reviews: 588, tone: "sky", badge: "New",
    description: "Lightweight acetate frames with polarised UV400 lenses and a scratch-resistant coating.",
    highlights: ["Polarised", "UV400", "Acetate frame", "Hard case included"],
    colors: ["#1f2937", "#b45309"], stock: 47,
  },
  {
    id: "p-card-wallet", sku: "AC-6004", name: "Slim Card Wallet", category: "accessories",
    price: "1099.00", rating: 4.5, reviews: 802, tone: "indigo",
    description: "RFID-blocking minimalist wallet that holds up to eight cards and a few folded notes.",
    highlights: ["RFID blocking", "Holds 8 cards", "Vegetable-tanned leather", "Pull tab"],
    colors: ["#1e3a8a", "#78350f", "#111827"], stock: 160,
  },
];

export const HERO_SLIDES: HeroSlide[] = [
  {
    eyebrow: "New season", title: "Sound that moves with you",
    text: "Wireless audio and smart wearables, now up to 30% off for a limited time.",
    cta: "Shop electronics", category: "electronics", tone: "indigo",
  },
  {
    eyebrow: "Fresh drop", title: "Wear the weekend",
    text: "Linen, denim and light layers built for long days and warm evenings.",
    cta: "Explore fashion", category: "fashion", tone: "rose",
  },
  {
    eyebrow: "Make it home", title: "Slow mornings, softer evenings",
    text: "Handmade ceramics, cozy throws and everything for your favourite corner.",
    cta: "Shop home", category: "home", tone: "amber",
  },
  {
    eyebrow: "Move more", title: "Gear up for every trail",
    text: "Backpacks, bottles and training essentials — free shipping on all sports orders.",
    cta: "Shop sports", category: "sports", tone: "emerald",
  },
];

export const TESTIMONIALS = [
  { name: "Ananya R.", city: "Bengaluru", text: "Ordered the Aurora headphones on a Monday, had them Wednesday. Packaging was lovely and the sound is unreal." },
  { name: "Rahul M.", city: "Pune", text: "The denim jacket fits perfectly. Exchange for a different size took two days — no questions asked." },
  { name: "Sneha K.", city: "Delhi", text: "My go-to for gifts. The bath ritual set was a hit and it arrived beautifully wrapped." },
  { name: "Arjun P.", city: "Chennai", text: "Great prices on everyday stuff and the deals actually feel like deals. Checkout is quick too." },
  { name: "Meera S.", city: "Mumbai", text: "Customer support sorted a delayed delivery in minutes. Rare to see that kind of care." },
];

export const FAQS: { group: string; items: { q: string; a: string }[] }[] = [
  {
    group: "Orders & payment",
    items: [
      { q: "Which payment methods do you accept?", a: "UPI, all major credit and debit cards, net banking and cash on delivery for eligible pincodes." },
      { q: "Can I change or cancel my order?", a: "You can cancel any order before it is shipped from your order page. Once shipped, you can request a return after delivery." },
      { q: "Do I need an account to order?", a: "No — guest checkout is available. Creating an account lets you track orders and keep a wishlist across devices." },
    ],
  },
  {
    group: "Shipping",
    items: [
      { q: "How long does delivery take?", a: "Metro cities usually receive orders in 2–3 business days and other locations in 4–7 business days." },
      { q: "Is shipping free?", a: "Shipping is free on orders above ₹999. A flat ₹79 fee applies to smaller orders." },
      { q: "Do you ship internationally?", a: "We currently ship within India only. International shipping is on our roadmap." },
    ],
  },
  {
    group: "Returns & refunds",
    items: [
      { q: "What is your return policy?", a: "Most items can be returned within 15 days of delivery in their original condition. Beauty products must be unopened." },
      { q: "When will I get my refund?", a: "Refunds are issued to the original payment method within 5–7 business days after we receive the return." },
    ],
  },
];

export const POLICIES: Record<string, { title: string; updated: string; sections: { heading: string; body: string }[] }> = {
  shipping: {
    title: "Shipping Policy",
    updated: "October 2026",
    sections: [
      { heading: "Delivery timelines", body: "Orders are dispatched within 24 hours on business days. Metro cities receive deliveries in 2–3 business days; other serviceable pincodes in 4–7 business days." },
      { heading: "Shipping charges", body: "Shipping is free on orders above ₹999. Orders below that carry a flat ₹79 shipping fee, shown at checkout before you pay." },
      { heading: "Tracking", body: "As soon as your order ships you will receive an email with a tracking link. You can also see live status on your orders page." },
    ],
  },
  returns: {
    title: "Returns & Refunds",
    updated: "October 2026",
    sections: [
      { heading: "Return window", body: "You can return most products within 15 days of delivery, provided they are unused and in original packaging with tags attached." },
      { heading: "Non-returnable items", body: "Opened beauty and personal-care products, gift cards and items marked final sale cannot be returned for hygiene and safety reasons." },
      { heading: "Refunds", body: "Once your return passes inspection, the refund is issued to your original payment method within 5–7 business days. Cash-on-delivery orders are refunded by bank transfer." },
    ],
  },
  privacy: {
    title: "Privacy Policy",
    updated: "October 2026",
    sections: [
      { heading: "What we collect", body: "We collect the details you give us at checkout — name, contact information and delivery address — along with basic browsing data that helps the store work, such as your cart." },
      { heading: "How we use it", body: "Your information is used to process orders, provide support and, only if you opt in, send offers. We never sell your personal data." },
      { heading: "Your choices", body: "You can request a copy of your data or ask us to delete it at any time by contacting support." },
    ],
  },
  terms: {
    title: "Terms of Service",
    updated: "October 2026",
    sections: [
      { heading: "Using the store", body: "By placing an order you confirm that the information you provide is accurate and that you are authorised to use the chosen payment method." },
      { heading: "Pricing", body: "Prices include applicable taxes unless stated otherwise. In the rare case of a pricing error we will contact you before shipping and you may cancel for a full refund." },
      { heading: "Liability", body: "Our liability for any order is limited to the amount paid for that order, to the extent permitted by law." },
    ],
  },
};

/* ---- local imagery (downloaded stock photos, see apps/web/public/images/MANIFEST.md) ---- */

const IMAGE_BASE = "/images";

export function productImage(productId: string): string {
  return `${IMAGE_BASE}/products/${productId}.jpg`;
}

export function categoryImage(categorySlug: string): string {
  return `${IMAGE_BASE}/categories/${categorySlug}.jpg`;
}

export function heroImage(categorySlug: string | undefined): string {
  return `${IMAGE_BASE}/hero/${categorySlug ?? "electronics"}.jpg`;
}

export const MAP_IMAGE = `${IMAGE_BASE}/contact/map.jpg`;

export const FREE_SHIPPING_THRESHOLD = 999;
export const FLAT_SHIPPING = 79;

export function categoryBySlug(slug: string | undefined): DemoCategory | undefined {
  return CATEGORIES.find((category) => category.slug === slug);
}

export function productById(id: string): DemoProduct | undefined {
  return PRODUCTS.find((product) => product.id === id);
}

export function productsIn(category: string): DemoProduct[] {
  return PRODUCTS.filter((product) => product.category === category);
}

/** Percentage saved versus the compare-at price, rounded down. */
export function discountPercent(product: DemoProduct): number | null {
  if (!product.compareAt) return null;
  const was = Number(product.compareAt);
  const now = Number(product.price);
  if (!(was > now)) return null;
  return Math.floor(((was - now) / was) * 100);
}
