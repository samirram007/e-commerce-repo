import { createFileRoute } from "@tanstack/react-router";
import { GatewaysPage } from "../../features/payments/GatewaysPage";

/** Payment gateway configuration (admin panel). */
export const Route = createFileRoute("/_protected/payment-gateways")({ component: GatewaysPage });
