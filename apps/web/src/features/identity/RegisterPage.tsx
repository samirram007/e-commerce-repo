import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Button, Card, ErrorBanner, Field, Input, PageHeader } from "../../components/ui";
import { fieldErrors } from "../../lib/zod-utils";
import { safeRedirect } from "../../lib/redirect";
import { useAuth } from "../../auth/auth-context";
import { registerShopper } from "../../services/identity";
import { STOREFRONT_SLUG } from "../storefront/store";
import { registerFormSchema } from "./schemas";

/**
 * Public signup for the storefront. The account is created for the store named
 * by the slug and signs in straight away, so the shopper lands back in the shop
 * with their cart and wishlist attached to the account.
 */
export function RegisterPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { redirect } = useSearch({ from: "/_guest/register" });
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    setError(null);
    const parsed = registerFormSchema.safeParse({ email, password, full_name: fullName });
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    setPending(true);
    try {
      await registerShopper({ slug: STOREFRONT_SLUG, ...parsed.data });
      await login(parsed.data.email, parsed.data.password);
    } catch (cause) {
      setError(cause);
      setPending(false);
      return;
    }
    setPending(false);
    navigate({ href: redirect ? safeRedirect(redirect) : "/shop" });
  }

  return (
    <div className="login-wrap">
      <PageHeader title="Create an account" description="Shop faster and keep your orders in one place." />
      <Card>
        <ErrorBanner error={error} />
        <Field label="Full name" error={errors.full_name}>
          <Input
            value={fullName}
            autoComplete="name"
            onChange={(event) => setFullName(event.target.value)}
          />
        </Field>
        <Field label="Email" error={errors.email}>
          <Input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        <Field label="Password" error={errors.password}>
          <Input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <Button onClick={submit} disabled={pending}>
            {pending ? "Please wait…" : "Create account"}
          </Button>
        </div>
        <p className="muted" style={{ marginTop: 12 }}>
          Already have an account?{" "}
          <Link
            to="/login"
            search={redirect ? { redirect } : {}}
            className="shop-text-link"
          >
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
