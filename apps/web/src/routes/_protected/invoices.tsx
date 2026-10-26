import { createFileRoute } from "@tanstack/react-router";
import { InvoicesPage } from "../../features/invoicing/InvoicesPage";

export const Route = createFileRoute("/_protected/invoices")({ component: InvoicesPage });
