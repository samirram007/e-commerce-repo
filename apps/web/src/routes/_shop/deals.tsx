import { createFileRoute } from "@tanstack/react-router";
import { DealsPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/deals")({ component: DealsPage });
