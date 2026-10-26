import { createFileRoute } from "@tanstack/react-router";
import { UsersPage } from "../../features/identity/UsersPage";

export const Route = createFileRoute("/_protected/users")({ component: UsersPage });
