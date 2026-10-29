/** Settings → Payment gateways.
 *
 * One card per provider (Razorpay, Stripe, mock): enable/disable, a TEST/LIVE
 * toggle (live asks for confirmation), separate test/live key sections where
 * secrets are write-only — the server only ever returns a "••••1234 saved"
 * hint — plus supported methods, priority, a connection test and the webhook
 * URL to paste into the provider dashboard.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  ErrorBanner,
  Field,
  Input,
  Modal,
  Spinner,
} from "../../components/ui";
import { Sheet } from "../../components/sheet";
import { RequirePermission } from "../../auth/guards";
import {
  gatewaysQueryOptions,
  useSwitchGatewayMode,
  useTestGateway,
  useUpdateGateway,
} from "./queries";
import {
  GATEWAY_METHODS,
  type Gateway,
  type GatewayMode,
  type GatewayUpdatePayload,
} from "./schemas";

/** A secret input: keep (untouched), set (typed), or clear on save. */
type SecretState = { kind: "keep" } | { kind: "set"; value: string } | { kind: "clear" };

interface ModeForm {
  public_key: string;
  secret: SecretState;
  webhook: SecretState;
}

interface GatewayForm {
  display_name: string;
  is_enabled: boolean;
  supported_methods: string[];
  priority: string;
  test: ModeForm;
  live: ModeForm;
}

function toForm(gateway: Gateway): GatewayForm {
  return {
    display_name: gateway.display_name,
    is_enabled: gateway.is_enabled,
    supported_methods: [...gateway.supported_methods],
    priority: String(gateway.priority),
    test: { public_key: gateway.test.public_key ?? "", secret: { kind: "keep" }, webhook: { kind: "keep" } },
    live: { public_key: gateway.live.public_key ?? "", secret: { kind: "keep" }, webhook: { kind: "keep" } },
  };
}

function secretPayload(state: SecretState): string | null | undefined {
  if (state.kind === "keep") return undefined; // omitted → keep existing
  if (state.kind === "clear") return null; // explicit null → clear
  return state.value;
}

/* ------------------------------------------------------------- secret field */

function SecretField({
  label,
  saved,
  hint,
  state,
  onChange,
}: {
  label: string;
  saved: boolean;
  hint: string | null;
  state: SecretState;
  onChange: (next: SecretState) => void;
}) {
  if (state.kind === "set") {
    return (
      <Field label={label}>
        <div className="toolbar" style={{ gap: 8 }}>
          <Input
            type="password"
            autoComplete="off"
            placeholder="Paste the secret"
            value={state.value}
            onChange={(event) => onChange({ kind: "set", value: event.target.value })}
            style={{ flex: 1 }}
          />
          <Button variant="ghost" onClick={() => onChange({ kind: "keep" })}>
            Cancel
          </Button>
        </div>
      </Field>
    );
  }
  if (state.kind === "clear") {
    return (
      <Field label={label}>
        <div className="toolbar" style={{ gap: 8 }}>
          <span className="muted">Will be cleared when you save</span>
          <Button variant="ghost" onClick={() => onChange({ kind: "keep" })}>
            Undo
          </Button>
        </div>
      </Field>
    );
  }
  return (
    <Field label={label}>
      <div className="toolbar" style={{ gap: 8 }}>
        <span className="muted" style={{ flex: 1 }}>
          {saved ? `••••${hint ?? ""} saved` : "Not set"}
        </span>
        <Button variant="secondary" onClick={() => onChange({ kind: "set", value: "" })}>
          {saved ? "Replace" : "Set"}
        </Button>
        {saved ? (
          <Button variant="ghost" onClick={() => onChange({ kind: "clear" })}>
            Clear
          </Button>
        ) : null}
      </div>
    </Field>
  );
}

/* ----------------------------------------------------- method multi-select */

/** Searchable sheet with checkboxes — the sheet-picker pattern, multi-select. */
function MethodsMultiSelect({
  value,
  onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const options = useMemo(
    () =>
      GATEWAY_METHODS.map((code) => ({
        value: code as string,
        label: code === "upi" ? "UPI" : "Credit / Debit card",
      })),
    [],
  );
  const filtered = options.filter((option) =>
    option.label.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const toggle = (code: string) => {
    onChange(
      value.includes(code) ? value.filter((item) => item !== code) : [...value, code],
    );
  };
  return (
    <div className="sheet-select">
      <div className="muted" style={{ marginBottom: 4 }}>
        Supported methods
      </div>
      <button type="button" className="sheet-trigger" onClick={() => setOpen(true)}>
        <span className={value.length ? undefined : "placeholder"}>
          {value.length
            ? value.map((code) => (code === "upi" ? "UPI" : "Card")).join(", ")
            : "Choose methods"}
        </span>
        <span className="chevron">▾</span>
      </button>
      <Sheet open={open} title="Supported methods" onClose={() => setOpen(false)}>
        <div className="sheet-search">
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search methods…"
          />
        </div>
        <div className="sheet-list">
          {filtered.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`sheet-option ${value.includes(option.value) ? "selected" : ""}`}
              onClick={() => toggle(option.value)}
            >
              <span>
                <input
                  type="checkbox"
                  readOnly
                  checked={value.includes(option.value)}
                  style={{ pointerEvents: "none" }}
                />{" "}
                {option.label}
              </span>
            </button>
          ))}
        </div>
      </Sheet>
    </div>
  );
}

/* ------------------------------------------------------------ provider card */

function GatewayCard({ gateway }: { gateway: Gateway }) {
  const [form, setForm] = useState<GatewayForm>(() => toForm(gateway));
  const [mode, setMode] = useState<GatewayMode>(gateway.mode);
  const [confirmLive, setConfirmLive] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // re-sync when the server data changes (after save / mode switch)
  useEffect(() => {
    setForm(toForm(gateway));
    setMode(gateway.mode);
  }, [gateway]);

  const update = useUpdateGateway();
  const switchMode = useSwitchGatewayMode();
  const test = useTestGateway();

  const setModeForm = (which: GatewayMode, patch: Partial<ModeForm>) =>
    setForm((current) => ({ ...current, [which]: { ...current[which], ...patch } }));

  function save() {
    const input: GatewayUpdatePayload = {
      is_enabled: form.is_enabled,
      display_name: form.display_name || gateway.display_name,
      mode,
      supported_methods: form.supported_methods,
      priority: Number(form.priority) || 0,
      test_public_key: form.test.public_key,
      live_public_key: form.live.public_key,
      test_secret: secretPayload(form.test.secret),
      test_webhook_secret: secretPayload(form.test.webhook),
      live_secret: secretPayload(form.live.secret),
      live_webhook_secret: secretPayload(form.live.webhook),
    };
    update.mutate({ provider: gateway.provider, input });
  }

  function requestMode(next: GatewayMode) {
    if (next === mode) return;
    if (next === "live") {
      setConfirmLive(true);
      return;
    }
    switchMode.mutate(
      { provider: gateway.provider, mode: next },
      { onSuccess: () => setTestResult(null) },
    );
  }

  function confirmLiveMode() {
    setConfirmLive(false);
    switchMode.mutate(
      { provider: gateway.provider, mode: "live" },
      { onSuccess: () => setTestResult(null) },
    );
  }

  function runTest() {
    setTestResult(null);
    test.mutate(gateway.provider, {
      onSuccess: (result) => setTestResult({ ok: result.ok, message: result.message }),
      onError: (error) =>
        setTestResult({
          ok: false,
          message: error instanceof Error ? error.message : "Connection test failed",
        }),
    });
  }

  async function copyWebhook() {
    try {
      await navigator.clipboard.writeText(gateway.webhook_url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard unavailable — the URL stays selectable in the input
    }
  }

  const keySection = (which: GatewayMode) => {
    const keys = which === "test" ? gateway.test : gateway.live;
    const local = form[which];
    return (
      <fieldset key={which} style={{ border: "1px solid var(--border, #e5e7eb)", borderRadius: 8, padding: 14, margin: 0 }}>
        <legend style={{ padding: "0 6px", fontWeight: 600, fontSize: 13 }}>
          {which === "test" ? "Test keys" : "Live keys"}
        </legend>
        <div className="grid-2">
          <Field label={which === "test" ? "Test public key" : "Live public key"}>
            <Input
              autoComplete="off"
              placeholder={gateway.provider === "stripe" ? "pk_test_…" : "rzp_test_…"}
              value={local.public_key}
              onChange={(event) => setModeForm(which, { public_key: event.target.value })}
            />
          </Field>
          <SecretField
            label={which === "test" ? "Test secret key" : "Live secret key"}
            saved={keys.has_secret}
            hint={keys.secret_hint}
            state={local.secret}
            onChange={(next) => setModeForm(which, { secret: next })}
          />
        </div>
        <SecretField
          label="Webhook secret"
          saved={keys.has_webhook_secret}
          hint={keys.webhook_secret_hint}
          state={local.webhook}
          onChange={(next) => setModeForm(which, { webhook: next })}
        />
      </fieldset>
    );
  };

  return (
    <Card
      title={
        <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>
          {gateway.display_name}
          <Badge tone={gateway.is_enabled ? "ok" : "bad"}>
            {gateway.is_enabled ? "enabled" : "disabled"}
          </Badge>
          <Badge tone={mode === "live" ? "bad" : "warn"}>{mode.toUpperCase()}</Badge>
        </span>
      }
      actions={
        <span className="toolbar" style={{ gap: 8 }}>
          <Button variant="secondary" onClick={runTest} disabled={test.isPending}>
            {test.isPending ? "Testing…" : "Test connection"}
          </Button>
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </span>
      }
    >
      <ErrorBanner error={update.error} />
      <ErrorBanner error={switchMode.error} />
      {testResult ? (
        <ErrorBanner
          error={testResult.ok ? null : new Error(testResult.message)}
        />
      ) : null}
      {testResult?.ok ? (
        <p className="muted" style={{ marginTop: 0 }}>
          ✓ {testResult.message}
        </p>
      ) : null}

      <div className="form-row" style={{ gap: 18, alignItems: "flex-end" }}>
        <label className="pill">
          <input
            type="checkbox"
            checked={form.is_enabled}
            onChange={(event) =>
              setForm((current) => ({ ...current, is_enabled: event.target.checked }))
            }
          />
          Enabled
        </label>

        <Field label="Mode">
          <div className="toolbar" style={{ gap: 6 }}>
            <Button
              variant={mode === "test" ? "primary" : "secondary"}
              onClick={() => requestMode("test")}
            >
              TEST
            </Button>
            <Button
              variant={mode === "live" ? "primary" : "secondary"}
              onClick={() => requestMode("live")}
            >
              LIVE
            </Button>
          </div>
        </Field>

        <Field label="Priority (lower wins)">
          <Input
            type="number"
            min={0}
            value={form.priority}
            onChange={(event) =>
              setForm((current) => ({ ...current, priority: event.target.value }))
            }
            style={{ maxWidth: 140 }}
          />
        </Field>

        <MethodsMultiSelect
          value={form.supported_methods}
          onChange={(supported_methods) =>
            setForm((current) => ({ ...current, supported_methods }))
          }
        />
      </div>

      <div style={{ display: "grid", gap: 14, marginTop: 14 }}>
        {keySection("test")}
        {keySection("live")}
      </div>

      <Field label="Webhook URL (paste into the provider dashboard)">
        <div className="toolbar" style={{ gap: 8 }}>
          <Input readOnly value={gateway.webhook_url} style={{ flex: 1 }} />
          <Button variant="secondary" onClick={() => void copyWebhook()}>
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
      </Field>

      <Modal
        open={confirmLive}
        title={`Switch ${gateway.display_name} to LIVE?`}
        onClose={() => setConfirmLive(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmLive(false)}>
              Cancel
            </Button>
            <Button onClick={confirmLiveMode}>Switch to live</Button>
          </>
        }
      >
        <p>
          Live mode charges real money with the saved live keys. Make sure live
          keys are saved and your webhook URL points at this production API.
        </p>
        {!gateway.live.has_secret || !gateway.live.public_key ? (
          <p className="error-text">
            Live keys are not saved yet — the switch will be rejected until you
            enter them.
          </p>
        ) : null}
      </Modal>
    </Card>
  );
}

/* -------------------------------------------------------------------- tab */

function GatewaysContent() {
  const gateways = useQuery(gatewaysQueryOptions());
  if (gateways.isLoading) return <Spinner label="Loading gateways…" />;
  if (gateways.error) {
    return <ErrorBanner error={gateways.error} />;
  }
  return (
    <>
      <Card>
        <p className="muted" style={{ margin: 0 }}>
          Turn providers on or off, save separate test and live keys, and choose
          which provider handles each storefront payment method. Changes apply
          immediately — no restart or redeploy. Cash on delivery stays offline
          and is not affected.
        </p>
      </Card>
      {(gateways.data ?? []).map((gateway) => (
        <GatewayCard key={gateway.provider} gateway={gateway} />
      ))}
    </>
  );
}

export function PaymentGatewaysTab(): ReactNode {
  return (
    <RequirePermission permission="payments.manage">
      <GatewaysContent />
    </RequirePermission>
  );
}