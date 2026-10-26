/** Smaller public pages: wishlist, categories, deals, about, contact, FAQ, policies, order confirmation. */
import { useState, type FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowRight, Award, Check, ChevronDown, Clock, FileQuestion, Heart, Leaf, Mail, MapPin, PackageCheck, Phone, Send, Sparkles, Users,
} from "lucide-react";
import { z } from "zod";
import { fieldErrors } from "../../lib/zod-utils";
import {
  Countdown, EmptyState, ImagePlaceholder, money, PageHero, ProductGrid, ProductRail, Reveal, SectionHeader,
} from "./components";
import { CATEGORIES, discountPercent, FAQS, MAP_IMAGE, POLICIES, PRODUCTS, categoryImage, productById, productsIn } from "./demo-catalog";
import { useShop } from "./shop-state";

export function WishlistPage() {
  const { wishlist } = useShop();
  const products = wishlist.flatMap((id) => productById(id) ?? []);
  return (
    <>
      <PageHero title="Your wishlist" text={products.length ? `${products.length} saved item${products.length === 1 ? "" : "s"}` : undefined} tone="rose" />
      <div className="shop-container section">
        {products.length ? (
          <ProductGrid products={products} />
        ) : (
          <EmptyState
            icon={<Heart aria-hidden />}
            title="No saved items yet"
            text="Tap the heart on any product to keep it here for later."
            action={<Link to="/shop" className="btn-primary">Discover products</Link>}
          />
        )}
      </div>
    </>
  );
}

export function CategoriesPage() {
  return (
    <>
      <PageHero title="All categories" text="Find exactly what you're after — or something you didn't know you needed." tone="violet" />
      <div className="shop-container section">
        {CATEGORIES.map((category, i) => {
          const items = productsIn(category.slug);
          return (
            <section key={category.slug} className="category-block">
              <Reveal className={`category-banner tone-${category.tone} ${i % 2 ? "reverse" : ""}`}>
                <div>
                  <span className="eyebrow">{items.length} products</span>
                  <h2>{category.name}</h2>
                  <p>{category.blurb}</p>
                  <Link to="/shop" search={{ category: category.slug }} className="btn-primary">
                    Shop {category.name} <ArrowRight aria-hidden />
                  </Link>
                </div>
                <ImagePlaceholder tone={category.tone} label={`${category.name} banner`} className="zoomable" src={categoryImage(category.slug)} />
              </Reveal>
              <ProductRail products={items} />
            </section>
          );
        })}
      </div>
    </>
  );
}

export function DealsPage() {
  const deals = PRODUCTS.filter((p) => p.compareAt).sort((a, b) => (discountPercent(b) ?? 0) - (discountPercent(a) ?? 0));
  const limited = PRODUCTS.filter((p) => p.badge === "Limited");
  return (
    <>
      <section className="page-hero tone-orange deals-hero">
        <span className="blob blob-a" />
        <span className="blob blob-b" />
        <div className="shop-container">
          <span className="eyebrow light fade-up"><Sparkles aria-hidden /> Festive sale</span>
          <h1 className="fade-up delay-1">Up to 30% off, today only</h1>
          <div className="fade-up delay-2"><Countdown /></div>
        </div>
      </section>
      <div className="shop-container section">
        <SectionHeader eyebrow="Biggest savings first" title="Today's deals" />
        <ProductGrid products={deals} />
      </div>
      <div className="shop-container section">
        <SectionHeader eyebrow="While stocks last" title="Limited editions" />
        <ProductRail products={limited} />
      </div>
    </>
  );
}

const VALUES = [
  { icon: Award, title: "Quality first", text: "Every product is tested by our team before it earns a spot in the store." },
  { icon: Leaf, title: "Responsibly made", text: "We favour makers using recycled materials and plastic-free packaging." },
  { icon: Users, title: "People-powered", text: "A small team obsessed with making online shopping feel personal again." },
];

const STATS = [
  { value: "250k+", label: "Happy customers" },
  { value: "19k", label: "Pincodes served" },
  { value: "4.7★", label: "Average rating" },
  { value: "48h", label: "Average delivery" },
];

export function AboutPage() {
  return (
    <>
      <PageHero title="Our story" text="Shopora started in 2019 with a simple idea: fewer, better things — delivered with care." tone="emerald" />
      <div className="shop-container section">
        <div className="split">
          <Reveal>
            <span className="eyebrow">Who we are</span>
            <h2 className="section-title">Curated by people, not algorithms</h2>
            <p className="lead">
              We work directly with independent brands and makers across India to bring you products we'd happily use ourselves.
              No endless scrolling through look-alikes — just a thoughtful selection, honest prices and service that actually helps.
            </p>
            <Link to="/shop" className="btn-primary">Shop the collection <ArrowRight aria-hidden /></Link>
          </Reveal>
          <Reveal delay={120}>
            <ImagePlaceholder tone="emerald" label="Team photo" ratio="4 / 3" className="rounded-lg float" />
          </Reveal>
        </div>
      </div>
      <div className="shop-container section stats">
        {STATS.map((stat, i) => (
          <Reveal key={stat.label} delay={i * 80} className="stat">
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </Reveal>
        ))}
      </div>
      <div className="shop-container section">
        <SectionHeader eyebrow="What we believe" title="Our values" />
        <div className="value-grid">
          {VALUES.map((value, i) => (
            <Reveal key={value.title} delay={i * 100} className="value-card">
              <span className="perk-icon"><value.icon aria-hidden /></span>
              <h3>{value.title}</h3>
              <p>{value.text}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </>
  );
}

const contactSchema = z.object({
  name: z.string().trim().min(2, "Enter your name"),
  email: z.email("Enter a valid email"),
  message: z.string().trim().min(10, "Tell us a little more (10+ characters)"),
});

export function ContactPage() {
  const { notify } = useShop();
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [sent, setSent] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = contactSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    setSent(true);
    notify("Message sent — we'll reply within a day");
  }

  const cards = [
    { icon: Phone, title: "Call us", text: "+91 80 4000 1234", sub: "Mon–Sat, 9am–8pm" },
    { icon: Mail, title: "Email", text: "hello@shopora.example", sub: "Replies within 24 hours" },
    { icon: MapPin, title: "Visit", text: "42 Market Street, Bengaluru", sub: "Studio open on weekends" },
    { icon: Clock, title: "Order help", text: "Track, cancel or return", sub: "Available 24/7 online" },
  ];

  return (
    <>
      <PageHero title="Get in touch" text="Questions about an order, a product or a partnership? We'd love to hear from you." tone="sky" />
      <div className="shop-container section">
        <div className="contact-cards">
          {cards.map((card, i) => (
            <Reveal key={card.title} delay={i * 80} className="value-card">
              <span className="perk-icon"><card.icon aria-hidden /></span>
              <h3>{card.title}</h3>
              <p><strong>{card.text}</strong><br />{card.sub}</p>
            </Reveal>
          ))}
        </div>
        <div className="split">
          <Reveal className="form-card">
            {sent ? (
              <div className="sent">
                <span className="success-check"><Check aria-hidden /></span>
                <h3>Thanks, {form.name.split(" ")[0]}!</h3>
                <p>We've received your message and will get back to you at {form.email}.</p>
                <button type="button" className="btn-ghost" onClick={() => { setSent(false); setForm({ name: "", email: "", message: "" }); }}>
                  Send another
                </button>
              </div>
            ) : (
              <form onSubmit={submit} noValidate>
                <h3>Send us a message</h3>
                {(["name", "email"] as const).map((key) => (
                  <label key={key} className={`form-field ${errors[key] ? "has-error" : ""}`}>
                    <span>{key === "name" ? "Your name" : "Email"}</span>
                    <input type={key === "email" ? "email" : "text"} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
                    {errors[key] ? <small className="field-error">{errors[key]}</small> : null}
                  </label>
                ))}
                <label className={`form-field ${errors.message ? "has-error" : ""}`}>
                  <span>Message</span>
                  <textarea rows={5} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
                  {errors.message ? <small className="field-error">{errors.message}</small> : null}
                </label>
                <button type="submit" className="btn-primary">Send message <Send aria-hidden /></button>
              </form>
            )}
          </Reveal>
          <Reveal delay={120}>
            <ImagePlaceholder tone="sky" label="Map" ratio="4 / 3" className="rounded-lg" src={MAP_IMAGE} />
          </Reveal>
        </div>
      </div>
    </>
  );
}

export function FaqPage() {
  const [open, setOpen] = useState<string | null>(FAQS[0]?.items[0]?.q ?? null);
  return (
    <>
      <PageHero title="Help & FAQ" text="Quick answers to the questions we hear most." tone="violet" />
      <div className="shop-container section faq">
        {FAQS.map((group, gi) => (
          <Reveal key={group.group} delay={gi * 80} className="faq-group">
            <h2>{group.group}</h2>
            {group.items.map((item) => {
              const isOpen = open === item.q;
              return (
                <div key={item.q} className={`faq-item ${isOpen ? "open" : ""}`}>
                  <button type="button" onClick={() => setOpen(isOpen ? null : item.q)} aria-expanded={isOpen}>
                    {item.q}
                    <ChevronDown aria-hidden />
                  </button>
                  <div className="faq-answer"><div><p>{item.a}</p></div></div>
                </div>
              );
            })}
          </Reveal>
        ))}
        <Reveal className="faq-cta">
          <FileQuestion aria-hidden />
          <div>
            <strong>Still need help?</strong>
            <span>Our team usually replies within a few hours.</span>
          </div>
          <Link to="/contact" className="btn-primary">Contact us</Link>
        </Reveal>
      </div>
    </>
  );
}

export function PolicyPage({ slug }: { slug: string }) {
  const policy = POLICIES[slug];
  if (!policy) {
    return (
      <div className="shop-container section">
        <EmptyState icon={<FileQuestion aria-hidden />} title="Page not found" text="That policy doesn't exist." action={<Link to="/faq" className="btn-primary">Visit help centre</Link>} />
      </div>
    );
  }
  return (
    <>
      <PageHero title={policy.title} text={`Last updated ${policy.updated}`} tone="slate" />
      <div className="shop-container section policy">
        <nav className="policy-nav">
          {Object.entries(POLICIES).map(([key, p]) => (
            <Link key={key} to="/policies/$slug" params={{ slug: key }} className={key === slug ? "active" : ""}>{p.title}</Link>
          ))}
        </nav>
        <article key={slug}>
          {policy.sections.map((section, i) => (
            <Reveal key={section.heading} delay={i * 80} className="policy-section">
              <h2>{section.heading}</h2>
              <p>{section.body}</p>
            </Reveal>
          ))}
        </article>
      </div>
    </>
  );
}

export function OrderSuccessPage({ order, total }: { order?: string; total?: string }) {
  return (
    <div className="shop-container section">
      <div className="order-success">
        <div className="confetti" aria-hidden>
          {Array.from({ length: 18 }, (_, i) => <span key={i} style={{ "--i": i } as React.CSSProperties} />)}
        </div>
        <span className="success-check big"><PackageCheck aria-hidden /></span>
        <h1>Order placed!</h1>
        <p>
          Thank you for shopping with us. {order ? <>Your order <strong>{order}</strong></> : "Your order"}
          {total ? <> for <strong>{money(total)}</strong></> : null} is confirmed and a receipt is on its way to your inbox.
        </p>
        <div className="deal-actions center">
          <Link to="/shop" className="btn-primary">Continue shopping <ArrowRight aria-hidden /></Link>
          <Link to="/" className="btn-ghost">Back to home</Link>
        </div>
      </div>
      <section className="section">
        <SectionHeader eyebrow="Picked for you" title="You might like these next" />
        <ProductRail products={PRODUCTS.filter((p) => p.badge === "New")} />
      </section>
    </div>
  );
}
