import { createFileRoute } from "@tanstack/react-router";
import { LoginPage } from "../../features/identity/LoginPage";

export const Route = createFileRoute("/_guest/login")({ component: LoginPage });
