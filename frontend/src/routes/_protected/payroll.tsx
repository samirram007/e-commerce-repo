import { createFileRoute } from "@tanstack/react-router";
import { PayrollPage } from "../../features/payroll/PayrollPage";

export const Route = createFileRoute("/_protected/payroll")({ component: PayrollPage });
