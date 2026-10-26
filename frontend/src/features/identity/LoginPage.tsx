import { useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { Button, Card, ErrorBanner, Field, Input, PageHeader } from "../../components/ui";
import { fieldErrors } from "../../lib/zod-utils";
import { safeRedirect } from "../../lib/redirect";
import { useAuth } from "../../auth/auth-context";
import { bootstrapFormSchema, loginFormSchema } from "./schemas";

type Mode = "login" | "bootstrap";

export function LoginPage() {
  const navigate = useNavigate();
  const { login, bootstrap } = useAuth();
  const { redirect } = useSearch({ from: "/_guest/login" });
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setErrors({});
    setError(null);
    setPassword("");
  }

  async function submit() {
    setError(null);

    if (mode === "login") {
      const parsed = loginFormSchema.safeParse({ email, password });
      if (!parsed.success) {
        setErrors(fieldErrors(parsed.error));
        return;
      }
      setErrors({});
      setPending(true);
      try {
        await login(parsed.data.email, parsed.data.password);
      } catch (cause) {
        setError(cause);
        setPending(false);
        return;
      }
      setPending(false);
<<<<<<< HEAD
      navigate({ href: safeRedirect(redirect) });
=======
      navigate({ to: "/dashboard" });
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
      return;
    }

    const parsed = bootstrapFormSchema.safeParse({ email, password, full_name: fullName });
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    setPending(true);
    try {
      await bootstrap(parsed.data.email, parsed.data.password, parsed.data.full_name);
    } catch (cause) {
      setError(cause);
      setPending(false);
      return;
    }
    setPending(false);
<<<<<<< HEAD
    navigate({ href: safeRedirect(redirect) });
=======
    navigate({ to: "/dashboard" });
>>>>>>> 54e515d3b6aaf64e97863aaa7cbacda772c82740
  }

  return (
    <div className="login-wrap">
      <PageHeader
        title={mode === "login" ? "Sign in" : "First-time setup"}
        description={
          mode === "login"
            ? "Use your ERP account to continue."
            : "Create the very first platform administrator."
        }
      />
      <Card>
        <ErrorBanner error={error} />
        <Field label="Email" error={errors.email}>
          <Input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        {mode === "bootstrap" ? (
          <Field label="Full name" error={errors.full_name}>
            <Input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </Field>
        ) : null}
        <Field label="Password" error={errors.password}>
          <Input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <Button onClick={submit} disabled={pending}>
            {pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create admin"}
          </Button>
          <Button
            variant="secondary"
            disabled={pending}
            onClick={() => switchMode(mode === "login" ? "bootstrap" : "login")}
          >
            {mode === "login" ? "First-time setup" : "Back to sign in"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
