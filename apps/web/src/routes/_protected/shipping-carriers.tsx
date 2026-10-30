import { createFileRoute } from "@tanstack/react-router";
import { CarriersPage } from "../../features/delivery/CarriersPage";

/** Third-party shipping carrier configuration (admin panel). */
export const Route = createFileRoute("/_protected/shipping-carriers")({ component: CarriersPage });
