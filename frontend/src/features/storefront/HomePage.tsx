<<<<<<< HEAD
import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  categoriesQueryOptions,
  productsQueryOptions,
  trendingQueryOptions,
} from "./queries";
import { ProductRail } from "./ProductRail";
import { EmptyState, Spinner } from "../../components/ui";
import { useStore } from "./store-context";
import type { ShopCategory } from "./types";

function CategoryRail({ category }: { category: ShopCategory }) {
  const products = useQuery(
    productsQueryOptions({ category: category.id, sort: "newest", limit: 8 }),
  );

  return (
    <ProductRail
      title={`Top picks in ${category.name}`}
      subtitle={`${category.product_count} product${category.product_count === 1 ? "" : "s"}`}
      products={products.data?.items}
      loading={products.isLoading}
      error={products.isError ? products.error : undefined}
      viewAll={{ category: category.id }}
      emptyMessage="Nothing in this category yet."
    />
  );
}

export function HomePage() {
  const categories = useQuery(categoriesQueryOptions());
  const trending = useQuery(trendingQueryOptions(8));
  const newest = useQuery(productsQueryOptions({ sort: "newest", limit: 8 }));
  const budget = useQuery(productsQueryOptions({ sort: "price_asc", limit: 8 }));
  const { store } = useStore();

  // Largest departments get their own rail (parents already include children).
  const topCategories = useMemo(
    () =>
      [...(categories.data ?? [])]
        .filter((c) => c.product_count > 0)
        .sort((a, b) => b.product_count - a.product_count || a.name.localeCompare(b.name))
        .slice(0, 3),
    [categories.data],
  );

  return (
    <div className="shop-page">
      <section className="shop-hero">
        <span className="shop-hero-eyebrow">Welcome</span>
        <h1 className="shop-hero-title">{store?.name ?? "The store"}</h1>
        <p className="shop-hero-sub">
          Browse the catalog, save what you love, and check out in a couple of clicks.
        </p>
        <div className="shop-hero-actions">
          <Link to="/shop/products" className="btn shop-hero-cta">
            Shop all products
          </Link>
          <a href="#categories" className="btn secondary shop-hero-cta">
            Browse categories
          </a>
        </div>
        <div className="shop-hero-badges">
          {store?.allow_guest_checkout ? <span className="badge ok">Guest checkout</span> : null}
          <span className="badge">Prices in {store?.currency ?? "INR"}</span>
          <span className="badge">Pincode delivery check</span>
        </div>
      </section>

      <section className="shop-section" id="categories">
        <div className="shop-section-head">
          <h2>Categories</h2>
          <Link to="/shop/products" className="shop-text-link">
            All products →
          </Link>
        </div>
        {categories.isLoading ? (
          <Spinner />
        ) : categories.isError ? (
          <EmptyState title="Could not load categories" />
        ) : (categories.data?.length ?? 0) === 0 ? (
          <EmptyState title="No categories yet" />
        ) : (
          <div className="shop-category-grid">
            {categories.data!.map((c) => (
              <Link
                key={c.id}
                to="/shop/products"
                search={{ category: c.id }}
                className="shop-category-card"
              >
                <span className="shop-category-name">{c.name}</span>
                <span className="muted">
                  {c.product_count} item{c.product_count === 1 ? "" : "s"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <ProductRail
        title="Trending now"
        subtitle="What other shoppers are viewing"
        products={trending.data}
        loading={trending.isLoading}
        error={trending.isError ? trending.error : undefined}
        emptyMessage="No trending products yet."
      />

      <ProductRail
        title="New arrivals"
        subtitle="Freshly added to the catalog"
        products={newest.data?.items}
        loading={newest.isLoading}
        error={newest.isError ? newest.error : undefined}
        viewAll={{ sort: "newest" }}
      />

      <ProductRail
        title="Budget picks"
        subtitle="Great value, lowest price first"
        products={budget.data?.items}
        loading={budget.isLoading}
        error={budget.isError ? budget.error : undefined}
        viewAll={{ sort: "price_asc" }}
      />

      {topCategories.map((category) => (
        <CategoryRail key={category.id} category={category} />
      ))}
    </div>
=======
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
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
  );
}
