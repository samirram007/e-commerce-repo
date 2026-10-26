import { createFileRoute } from "@tanstack/react-router";
import { RolesPage } from "../../features/identity/RolesPage";

export const Route = createFileRoute("/_protected/roles")({ component: RolesPage });
