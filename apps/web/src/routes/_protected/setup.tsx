import { createFileRoute } from "@tanstack/react-router";
import { SetupWizard } from "../../features/settings/SetupWizard";

export const Route = createFileRoute("/_protected/setup")({ component: SetupWizard });
