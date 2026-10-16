import { createFileRoute } from "@tanstack/react-router";
import { ShipmentsPage } from "../../features/fulfillment/ShipmentsPage";

export const Route = createFileRoute("/_protected/shipments")({ component: ShipmentsPage });
