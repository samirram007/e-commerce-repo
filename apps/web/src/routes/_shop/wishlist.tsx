import { createFileRoute } from "@tanstack/react-router";
import { WishlistPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/wishlist")({ component: WishlistPage });
