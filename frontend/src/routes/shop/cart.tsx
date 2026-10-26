import { createFileRoute } from "@tanstack/react-router";
import { CartPage } from "../../features/storefront/CartPage";

export const Route = createFileRoute("/shop/cart")({
  component: CartPage,
});