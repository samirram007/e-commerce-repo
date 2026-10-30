import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { LoginPage } from "../../features/identity/LoginPage";

/** `?redirect=…` is where the shopper came from; validated as a plain string. */
const loginSearchSchema = z.object({
  redirect: z.string().optional(),
});

export const Route = createFileRoute("/_guest/login")({
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => {
    const parsed = loginSearchSchema.safeParse(search);
    return parsed.success ? parsed.data : {};
  },
  component: LoginPage,
});
