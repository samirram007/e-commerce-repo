import { createFileRoute } from "@tanstack/react-router";
import { CartPage } from "../../features/storefront/CartPage";

export const Route = createFileRoute("/_shop/cart")({ component: CartPage });
