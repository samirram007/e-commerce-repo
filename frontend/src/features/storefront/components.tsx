/** Shared building blocks for the public storefront: placeholders, cards, sliders, reveal animations. */
import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight, ChevronLeft, ChevronRight, Heart, ImageIcon, Quote, ShoppingBag, Star } from "lucide-react";
import { formatMoney } from "../../lib/format";
import {
  categoryBySlug,
  discountPercent,
  HERO_SLIDES,
  heroImage,
  productImage,
  TESTIMONIALS,
  type DemoProduct,
  type Tone,
} from "./demo-catalog";
import { useShop } from "./shop-state";

export function money(value: string | number): string {
  return formatMoney(value, "INR");
}

/**
 * Image slot. When `src` is given the real photo is rendered; on a load error it
 * falls back to the tinted placeholder as before.
 */
export function ImagePlaceholder({
  tone,
  label,
  className = "",
  ratio,
  src,
}: {
  tone: Tone;
  label?: string;
  className?: string;
  ratio?: string;
  src?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const showPhoto = src !== undefined && !failed;
  const style: CSSProperties | undefined = ratio ? { aspectRatio: ratio } : undefined;
  return (
    <div
      className={`img-ph tone-${tone} ${showPhoto ? "has-photo" : ""} ${className}`}
      style={style}
      role={showPhoto ? undefined : "img"}
      aria-label={showPhoto ? undefined : label ?? "Image placeholder"}
    >
      {showPhoto ? (
        <img src={src} alt={label ?? ""} loading="lazy" decoding="async" onError={() => setFailed(true)} />
      ) : (
        <>
          <ImageIcon className="img-ph-icon" aria-hidden />
          {label ? <span className="img-ph-label">{label}</span> : null}
        </>
      )}
    </div>
  );
}

/** Fades/slides children in the first time they scroll into view. */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li";
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as never}
      className={`reveal ${visible ? "is-visible" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}

export function Stars({ rating, reviews }: { rating: number; reviews?: number }) {
  return (
    <span className="stars" aria-label={`Rated ${rating} out of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} className={n <= Math.round(rating) ? "on" : ""} aria-hidden />
      ))}
      <span className="stars-num">{rating.toFixed(1)}</span>
      {reviews !== undefined ? <span className="stars-count">({reviews.toLocaleString("en-IN")})</span> : null}
    </span>
  );
}

export function Price({ product, large = false }: { product: DemoProduct; large?: boolean }) {
  const off = discountPercent(product);
  return (
    <span className={`price ${large ? "price-lg" : ""}`}>
      <span className="price-now">{money(product.price)}</span>
      {product.compareAt && off ? (
        <>
          <span className="price-was">{money(product.compareAt)}</span>
          <span className="price-off">{off}% off</span>
        </>
      ) : null}
    </span>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <Reveal className="section-head">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h2 className="section-title">{title}</h2>
      </div>
      {action}
    </Reveal>
  );
}

export function ProductCard({ product }: { product: DemoProduct }) {
  const { addToCart, toggleWishlist, isWishlisted } = useShop();
  const category = categoryBySlug(product.category);
  const saved = isWishlisted(product.id);

  return (
    <article className="product-card">
      <Link to="/shop/$productId" params={{ productId: product.id }} className="product-media">
        <ImagePlaceholder tone={product.tone} label={product.name} className="zoomable" src={productImage(product.id)} />
        {product.badge ? <span className={`chip chip-${product.badge.toLowerCase()}`}>{product.badge}</span> : null}
      </Link>
      <button
        type="button"
        className={`icon-btn wish-btn ${saved ? "active" : ""}`}
        aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
        aria-pressed={saved}
        onClick={() => toggleWishlist(product.id)}
      >
        <Heart aria-hidden />
      </button>
      <div className="product-body">
        <div className="product-cat">{category?.name}</div>
        <Link to="/shop/$productId" params={{ productId: product.id }} className="product-name">
          {product.name}
        </Link>
        <Stars rating={product.rating} reviews={product.reviews} />
        <div className="product-foot">
          <Price product={product} />
          <button
            type="button"
            className="icon-btn add-btn"
            aria-label={`Add ${product.name} to bag`}
            onClick={() => addToCart(product.id)}
          >
            <ShoppingBag aria-hidden />
          </button>
        </div>
      </div>
    </article>
  );
}

export function ProductGrid({ products }: { products: DemoProduct[] }) {
  return (
    <div className="product-grid">
      {products.map((product, index) => (
        <Reveal key={product.id} delay={(index % 4) * 70}>
          <ProductCard product={product} />
        </Reveal>
      ))}
    </div>
  );
}

/** Horizontally scrolling, snap-aligned carousel of product cards with arrow controls. */
export function ProductRail({ products }: { products: DemoProduct[] }) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const [edges, setEdges] = useState({ start: true, end: false });

  const updateEdges = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    setEdges({
      start: track.scrollLeft <= 4,
      end: track.scrollLeft + track.clientWidth >= track.scrollWidth - 4,
    });
  }, []);

  useEffect(() => {
    updateEdges();
    window.addEventListener("resize", updateEdges);
    return () => window.removeEventListener("resize", updateEdges);
  }, [updateEdges]);

  function scroll(direction: 1 | -1) {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: direction * track.clientWidth * 0.85, behavior: "smooth" });
  }

  return (
    <div className="rail">
      <button type="button" className="rail-arrow prev" onClick={() => scroll(-1)} disabled={edges.start} aria-label="Scroll left">
        <ChevronLeft aria-hidden />
      </button>
      <div className="rail-track" ref={trackRef} onScroll={updateEdges}>
        {products.map((product) => (
          <div className="rail-item" key={product.id}>
            <ProductCard product={product} />
          </div>
        ))}
      </div>
      <button type="button" className="rail-arrow next" onClick={() => scroll(1)} disabled={edges.end} aria-label="Scroll right">
        <ChevronRight aria-hidden />
      </button>
    </div>
  );
}

/** Autoplaying hero slideshow with arrows, dots and pause-on-hover. */
export function HeroSlider() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const count = HERO_SLIDES.length;

  const go = useCallback((next: number) => setIndex(((next % count) + count) % count), [count]);

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % count), 5500);
    return () => window.clearInterval(timer);
  }, [paused, count]);

  return (
    <section
      className="hero"
      aria-roledescription="carousel"
      aria-label="Featured collections"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="hero-track" style={{ transform: `translateX(-${index * 100}%)` }}>
        {HERO_SLIDES.map((slide, slideIndex) => (
          <div
            key={slide.title}
            className={`hero-slide tone-${slide.tone} ${slideIndex === index ? "is-active" : ""}`}
            aria-roledescription="slide"
            aria-label={`${slideIndex + 1} of ${count}`}
            aria-hidden={slideIndex !== index}
          >
            <div className="hero-copy">
              <span className="eyebrow light">{slide.eyebrow}</span>
              <h1>{slide.title}</h1>
              <p>{slide.text}</p>
              <Link
                to="/shop"
                search={{ category: slide.category }}
                className="btn-primary"
                tabIndex={slideIndex === index ? 0 : -1}
              >
                {slide.cta} <ArrowRight aria-hidden />
              </Link>
            </div>
            <div className="hero-art">
              <span className="blob blob-a" />
              <span className="blob blob-b" />
              <ImagePlaceholder tone={slide.tone} label="Campaign image" className="hero-img float" src={heroImage(slide.category)} />
            </div>
          </div>
        ))}
      </div>
      <button type="button" className="hero-arrow prev" onClick={() => go(index - 1)} aria-label="Previous slide">
        <ChevronLeft aria-hidden />
      </button>
      <button type="button" className="hero-arrow next" onClick={() => go(index + 1)} aria-label="Next slide">
        <ChevronRight aria-hidden />
      </button>
      <div className="hero-dots">
        {HERO_SLIDES.map((slide, dotIndex) => (
          <button
            key={slide.title}
            type="button"
            className={dotIndex === index ? "active" : ""}
            onClick={() => go(dotIndex)}
            aria-label={`Go to slide ${dotIndex + 1}`}
            aria-current={dotIndex === index}
          >
            {dotIndex === index && !paused ? <span className="dot-progress" key={index} /> : null}
          </button>
        ))}
      </div>
    </section>
  );
}

/** Crossfading customer testimonials. */
export function TestimonialSlider() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % TESTIMONIALS.length), 6000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="testimonials">
      <Quote className="testimonial-quote" aria-hidden />
      <div className="testimonial-stage">
        {TESTIMONIALS.map((testimonial, i) => (
          <figure key={testimonial.name} className={`testimonial ${i === index ? "is-active" : ""}`} aria-hidden={i !== index}>
            <blockquote>{testimonial.text}</blockquote>
            <figcaption>
              <span className="avatar-ph">{testimonial.name.charAt(0)}</span>
              <span>
                <strong>{testimonial.name}</strong>
                <span className="muted-text">{testimonial.city}</span>
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
      <div className="testimonial-dots">
        {TESTIMONIALS.map((testimonial, i) => (
          <button
            key={testimonial.name}
            type="button"
            className={i === index ? "active" : ""}
            onClick={() => setIndex(i)}
            aria-label={`Show review ${i + 1}`}
          />
        ))}
      </div>
    </div>
  );
}

/** Countdown to the next midnight, used for the deal-of-the-day banners. */
export function Countdown() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const end = new Date(now);
  end.setHours(24, 0, 0, 0);
  const remaining = Math.max(0, end.getTime() - now);
  const parts = [
    Math.floor(remaining / 3_600_000),
    Math.floor((remaining % 3_600_000) / 60_000),
    Math.floor((remaining % 60_000) / 1000),
  ];
  return (
    <div className="countdown" aria-label="Time left on today's deals">
      {parts.map((value, i) => (
        <span key={i} className="countdown-cell">
          <strong>{String(value).padStart(2, "0")}</strong>
          <small>{["hrs", "min", "sec"][i]}</small>
        </span>
      ))}
    </div>
  );
}

export function PageHero({ title, text, tone = "indigo" }: { title: string; text?: string; tone?: Tone }) {
  return (
    <section className={`page-hero tone-${tone}`}>
      <span className="blob blob-a" />
      <span className="blob blob-b" />
      <div className="shop-container">
        <h1 className="fade-up">{title}</h1>
        {text ? <p className="fade-up delay-1">{text}</p> : null}
      </div>
    </section>
  );
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty-state fade-up">
      <div className="empty-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{text}</p>
      {action}
    </div>
  );
}
