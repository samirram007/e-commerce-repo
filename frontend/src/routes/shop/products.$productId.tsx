import { createFileRoute } from "@tanstack/react-router";
import { ProductDetailPage } from "../../features/storefront/ProductDetailPage";

export const Route = createFileRoute("/shop/products/$productId")({
  component: ProductDetailRoute,
});

function ProductDetailRoute() {
  const { productId } = Route.useParams();
  return <ProductDetailPage productId={productId} />;
}