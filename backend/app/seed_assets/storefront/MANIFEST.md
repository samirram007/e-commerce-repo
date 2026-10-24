# Storefront imagery

35 photos downloaded from **Unsplash** (Unsplash License — free for commercial
use, attribution appreciated; see <https://unsplash.com/license>). All files are
JPEG, verified (format + size) at fetch time.

These images seed the backend storefront (`python -m app.seed`): each photo is
registered as a public `StoredFile` and served through
`/api/v1/storefront/shop/media/{company_id}/{file_id}`. The `tone` fields remain
as loading/error fallbacks in the frontend's `ImagePlaceholder` component.

## Attribution sources

| File | Source |
| --- | --- |
| products/p-aurora-headphones.jpg | unsplash.com/photos/photo-1505740420928-5e560c06d30e |
| products/p-pulse-watch.jpg | unsplash.com/photos/photo-1546868871-7041f2a55e12 |
| products/p-echo-speaker.jpg | unsplash.com/photos/_bWH-4OjrYA |
| products/p-nova-earbuds.jpg | unsplash.com/photos/5ba6j8d_oXY |
| products/p-linen-shirt.jpg | unsplash.com/photos/photo-1604176354204-9268737828e4 |
| products/p-denim-jacket.jpg | unsplash.com/photos/_BDBEP0ePQc |
| products/p-runner-sneakers.jpg | unsplash.com/photos/photo-1542291026-7eec264c27ff |
| products/p-wool-scarf.jpg | unsplash.com/photos/wHUizUx2pXM |
| products/p-ceramic-vase.jpg | unsplash.com/photos/4VbLmBnq4uQ |
| products/p-throw-blanket.jpg | unsplash.com/photos/jXsR51tcTjM |
| products/p-pour-over.jpg | unsplash.com/photos/uDFAD5PS-pI |
| products/p-desk-lamp.jpg | unsplash.com/photos/ZyXBmcdOLsc |
| products/p-glow-serum.jpg | unsplash.com/photos/cgd9z9as2Lc |
| products/p-night-cream.jpg | unsplash.com/photos/photo-1556228720-195a672e8a03 |
| products/p-bath-set.jpg | unsplash.com/photos/photo-1571781926291-c477ebfd024b |
| products/p-lip-trio.jpg | unsplash.com/photos/photo-1586495777744-4413f21062fa |
| products/p-yoga-mat.jpg | unsplash.com/photos/photo-1599901860904-17e6ed7083a0 |
| products/p-trail-backpack.jpg | unsplash.com/photos/photo-1553062407-98eeb64c6a62 |
| products/p-steel-bottle.jpg | unsplash.com/photos/axMEtSm42iQ |
| products/p-resistance-bands.jpg | unsplash.com/photos/IZOAOjvwhaM |
| products/p-leather-tote.jpg | unsplash.com/photos/5aitUudFKOA |
| products/p-minimal-watch.jpg | unsplash.com/photos/photo-1523275335684-37898b6baf30 |
| products/p-sunglasses.jpg | unsplash.com/photos/photo-1572635196237-14b3f281503f |
| products/p-card-wallet.jpg | unsplash.com/photos/na8l3EPqpvY |
| categories/electronics.jpg | unsplash.com/photos/photo-1498049794561-7780e7231661 |
| categories/fashion.jpg | unsplash.com/photos/photo-1445205170230-053b83016050 |
| categories/home.jpg | unsplash.com/photos/photo-1522708323590-d24dbb6b0267 |
| categories/beauty.jpg | unsplash.com/photos/photo-1596462502278-27bfdc403348 |
| categories/sports.jpg | unsplash.com/photos/UFs5bKHgo4U |
| categories/accessories.jpg | unsplash.com/photos/photo-1483985988355-763728e1935b |
| hero/electronics.jpg | unsplash.com/photos/photo-1546435770-a3e426bf472b |
| hero/fashion.jpg | unsplash.com/photos/A0YlCg2iu2k |
| hero/home.jpg | unsplash.com/photos/photo-1484101403633-562f891dc89a |
| hero/sports.jpg | unsplash.com/photos/photo-1571019613454-1cb2f99b2d8b |
| contact/map.jpg | unsplash.com/photos/photo-1524661135-423995f22d0b |

## Notes

- Product images are 900px wide, category/hero images 1600px wide.
- Image content follows the demo catalog in
  `frontend/src/features/storefront/demo-catalog.ts`: one image per product
  `id` (e.g. `p-aurora-headphones` → `images/products/p-aurora-headphones.jpg`),
  per category `slug`, per hero `category`, and a contact-page map image.
- If any photo turns out to be off-brand or needs replacing, re-run a fetch with
  the `/download` pattern used above:
  `https://unsplash.com/photos/<photo-id>/download?force=true&w=900`.
