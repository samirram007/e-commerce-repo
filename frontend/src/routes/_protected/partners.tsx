import { createFileRoute } from "@tanstack/react-router";
import { PartnersPage } from "../../features/partners/PartnersPage";

export const Route = createFileRoute("/_protected/partners")({ component: PartnersPage });
