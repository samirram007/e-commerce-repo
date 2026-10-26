import { Link } from "@tanstack/react-router";
import { ArrowRight, Headphones, RotateCcw, ShieldCheck, Truck } from "lucide-react";
import {
  Countdown,
  HeroSlider,
  ImagePlaceholder,
  Price,
  ProductGrid,
  ProductRail,
  Reveal,
  SectionHeader,
  TestimonialSlider,
} from "./components";
import { CATEGORIES, PRODUCTS, categoryImage, productImage, productsIn } from "./demo-catalog";
import { useShop } from "./shop-state";

const PERKS = [
  { icon: Truck, title: "Free shipping", text: "On every order above ₹999" },
  { icon: RotateCcw, title: "15-day returns", text: "No-fuss exchanges & refunds" },
  { icon: ShieldCheck, title: "Secure payments", text: "UPI, cards & cash on delivery" },
  { icon: Headphones, title: "Real humans", text: "Support 7 days a week" },
];

export function HomePage() {
  const { addToCart } = useShop();
  const bestsellers = [...PRODUCTS].sort((a, b) => b.reviews - a.reviews).slice(0, 10);
  const newArrivals = PRODUCTS.filter((product) => product.badge === "New").slice(0, 8);
  const deal = PRODUCTS.find((product) => product.id === "p-aurora-headphones") ?? PRODUCTS[0]!;

  return (
    <>
      <div className="shop-container">
        <HeroSlider />
      </div>

      <section className="shop-container perks">
        {PERKS.map((perk, i) => (
          <Reveal key={perk.title} delay={i * 80} className="perk">
            <span className="perk-icon"><perk.icon aria-hidden /></span>
            <div>
              <strong>{perk.title}</strong>
              <span>{perk.text}</span>
            </div>
          </Reveal>
        ))}
      </section>

      <section className="shop-container section">
        <SectionHeader
          eyebrow="Browse"
          title="Shop by category"
          action={<Link to="/categories" className="link-arrow">All categories <ArrowRight aria-hidden /></Link>}
        />
        <div className="category-grid">
          {CATEGORIES.map((category, i) => (
            <Reveal key={category.slug} delay={i * 70}>
              <Link to="/shop" search={{ category: category.slug }} className={`category-card tone-${category.tone}`}>
                <ImagePlaceholder tone={category.tone} className="zoomable" src={categoryImage(category.slug)} />
                <div className="category-info">
                  <strong>{category.name}</strong>
                  <span>{productsIn(category.slug).length} products</span>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="shop-container section">
        <SectionHeader
          eyebrow="Loved by thousands"
          title="Bestsellers"
          action={<Link to="/shop" search={{ sort: "popular" }} className="link-arrow">View all <ArrowRight aria-hidden /></Link>}
        />
        <Reveal>
          <ProductRail products={bestsellers} />
        </Reveal>
      </section>

      <section className="shop-container section">
        <Reveal className="deal-banner tone-indigo">
          <div className="deal-copy">
            <span className="eyebrow light">Deal of the day</span>
            <h2>{deal.name}</h2>
            <p>{deal.description}</p>
            <Price product={deal} large />
            <Countdown />
            <div className="deal-actions">
              <button type="button" className="btn-primary light" onClick={() => addToCart(deal.id)}>
                Add to bag
              </button>
              <Link to="/shop/$productId" params={{ productId: deal.id }} className="btn-ghost light">
                View details
              </Link>
            </div>
          </div>
          <div className="deal-art">
            <span className="blob blob-a" />
            <ImagePlaceholder tone="indigo" label="Product image" className="float" src={productImage(deal.id)} />
          </div>
        </Reveal>
      </section>

      <section className="shop-container section">
        <SectionHeader
          eyebrow="Just landed"
          title="New arrivals"
          action={<Link to="/shop" search={{ sort: "newest" }} className="link-arrow">Shop new <ArrowRight aria-hidden /></Link>}
        />
        <ProductGrid products={newArrivals} />
      </section>

      <section className="shop-container section promo-pair">
        <Reveal className="promo-tile tone-rose">
          <div>
            <span className="eyebrow">Fashion edit</span>
            <h3>Linen season is here</h3>
            <Link to="/shop" search={{ category: "fashion" }} className="link-arrow">Shop the edit <ArrowRight aria-hidden /></Link>
          </div>
          <ImagePlaceholder tone="rose" className="promo-img zoomable" src={categoryImage("fashion")} />
        </Reveal>
        <Reveal className="promo-tile tone-emerald" delay={120}>
          <div>
            <span className="eyebrow">Outdoors</span>
            <h3>Trail-ready essentials</h3>
            <Link to="/shop" search={{ category: "sports" }} className="link-arrow">Gear up <ArrowRight aria-hidden /></Link>
          </div>
          <ImagePlaceholder tone="emerald" className="promo-img zoomable" src={categoryImage("sports")} />
        </Reveal>
      </section>

      <section className="shop-container section">
        <SectionHeader eyebrow="Reviews" title="What our customers say" />
        <Reveal>
          <TestimonialSlider />
        </Reveal>
      </section>
    </>
  );
}
