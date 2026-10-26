import { createFileRoute } from "@tanstack/react-router";
import { FaqPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/faq")({ component: FaqPage });
