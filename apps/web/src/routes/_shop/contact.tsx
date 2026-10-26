import { createFileRoute } from "@tanstack/react-router";
import { ContactPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/contact")({ component: ContactPage });
