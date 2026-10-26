import { createFileRoute } from "@tanstack/react-router";
import { CategoriesPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/categories")({ component: CategoriesPage });
