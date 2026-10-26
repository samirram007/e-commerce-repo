import { createFileRoute } from "@tanstack/react-router";
import { PurchasingPage } from "../../features/purchasing/PurchasingPage";
export const Route = createFileRoute("/_protected/purchase-orders")({ component: PurchasingPage });
