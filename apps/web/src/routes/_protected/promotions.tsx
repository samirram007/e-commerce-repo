import { createFileRoute } from "@tanstack/react-router";
import { CouponsPage } from "../../features/promotions/CouponsPage";

export const Route = createFileRoute("/_protected/promotions")({ component: CouponsPage });
