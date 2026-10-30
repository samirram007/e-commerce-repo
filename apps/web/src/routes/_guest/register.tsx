import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { RegisterPage } from "../../features/identity/RegisterPage";

/** `?redirect=…` is where the shopper came from; validated as a plain string. */
const registerSearchSchema = z.object({
  redirect: z.string().optional(),
});

export const Route = createFileRoute("/_guest/register")({
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => {
    const parsed = registerSearchSchema.safeParse(search);
    return parsed.success ? parsed.data : {};
  },
  component: RegisterPage,
});
