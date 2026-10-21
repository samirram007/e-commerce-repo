import { createFileRoute } from "@tanstack/react-router";
import { ShopLayout } from "../features/storefront/ShopLayout";

/**
 * Pathless layout for the public storefront. No auth guard: every page under
 * it is reachable by anonymous visitors.
 */
export const Route = createFileRoute("/_shop")({ component: ShopLayout });
