import { createFileRoute } from "@tanstack/react-router";
import { ProductDetailPage } from "../../features/storefront/ProductDetailPage";

export const Route = createFileRoute("/_shop/shop/$productId")({
  component: function ProductRoute() {
    const { productId } = Route.useParams();
    // Keyed so gallery/quantity state resets when navigating between products.
    return <ProductDetailPage key={productId} productId={productId} />;
  },
});
