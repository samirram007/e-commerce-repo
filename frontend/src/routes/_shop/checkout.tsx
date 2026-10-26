import { createFileRoute } from "@tanstack/react-router";
import { CheckoutPage } from "../../features/storefront/CheckoutPage";

export const Route = createFileRoute("/_shop/checkout")({ component: CheckoutPage });
