import { createFileRoute } from "@tanstack/react-router";
import { AccountingPage } from "../../features/accounting/AccountingPage";

export const Route = createFileRoute("/_protected/accounting")({ component: AccountingPage });
