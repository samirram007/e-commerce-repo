import { createFileRoute } from "@tanstack/react-router";
import { ProductPage } from "../../features/storefront/ProductPage";

export const Route = createFileRoute("/_shop/shop/$productId")({
  component: function ProductRoute() {
    const { productId } = Route.useParams();
    // Keyed so gallery/quantity state resets when navigating between products.
    return <ProductPage key={productId} productId={productId} />;
  },
});
