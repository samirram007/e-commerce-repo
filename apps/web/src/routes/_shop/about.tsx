import { createFileRoute } from "@tanstack/react-router";
import { AboutPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/about")({ component: AboutPage });
