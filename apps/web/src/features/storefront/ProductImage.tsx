import { useMemo, useState } from "react";

/**
 * Product image with a deterministic generated placeholder.
 *
 * Products may carry an `image_url`; when absent — or when it fails to load —
 * we render a stable gradient tile seeded from the product identity so the
 * catalog never shows a blank or broken box.
 */
interface Props {
  name: string;
  sku: string;
  imageUrl?: string | null;
  /** Larger tile treatment for the product detail page. */
  large?: boolean;
}

/** FNV-1a: stable across reloads so a product always gets the same tile. */
function hashString(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "??";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function ProductImage({ name, sku, imageUrl, large = false }: Props) {
  const [failed, setFailed] = useState(false);

  const fallback = useMemo(() => {
    const hash = hashString(sku || name);
    const hue = hash % 360;
    const hue2 = (hue + 40) % 360;
    return {
      background: `linear-gradient(135deg, hsl(${hue} 70% 78%), hsl(${hue2} 62% 52%))`,
      initials: initialsOf(name),
    };
  }, [name, sku]);

  const tileClass = large ? "shop-img-tile shop-img-tile-lg" : "shop-img-tile";
  const showImage = !!imageUrl && !failed;

  return (
    <span className={large ? "shop-img-wrap shop-img-wrap-lg" : "shop-img-wrap"}>
      {showImage ? (
        <img
          className={large ? "shop-img shop-img-lg" : "shop-img"}
          src={imageUrl}
          alt={name}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : null}
      {!showImage ? (
        <span
          className={tileClass}
          style={{ background: fallback.background }}
          role="img"
          aria-label={name}
        >
          <span className="shop-img-initials">{fallback.initials}</span>
        </span>
      ) : null}
    </span>
  );
}
