import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, ErrorBanner, Field, Input, Modal, PageHeader, Spinner, StatusBadge, Textarea } from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { titleCase } from "../../lib/format";
import { gatewaysQueryOptions, useDeleteGateway, useSaveGateway } from "./gateway-queries";
import {
  GATEWAY_MODES,
  KIND_LABELS,
  type Gateway,
  type GatewayPayload,
} from "./gateway-schemas";

/** Editable copy of a gateway; credentials start blank (secret values are never sent). */
interface Draft {
  label: string;
  mode: string;
  priority: string;
  is_enabled: boolean;
  credentials: Record<string, string>;
  settings: Record<string, string | string[]>;
  extras: { key: string; value: string }[];
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function draftFrom(gateway: Gateway): Draft {
  const known = new Set(gateway.settings_fields.map((field) => field.key));
  const settings: Record<string, string | string[]> = {};
  for (const field of gateway.settings_fields) {
    const value = gateway.settings[field.key];
    settings[field.key] = field.type === "multi_select" ? (Array.isArray(value) ? value.map(String) : []) : stringValue(value);
  }
  // Anything the admin added themselves shows up as an extra key/value row.
  const extras = Object.entries(gateway.settings)
    .filter(([key]) => !known.has(key))
    .map(([key, value]) => ({ key, value: stringValue(value) }));
  return {
    label: gateway.display_label === gateway.label ? "" : gateway.display_label,
    mode: gateway.mode,
    priority: String(gateway.priority),
    is_enabled: gateway.is_enabled,
    credentials: {},
    settings,
    extras,
  };
}

function payloadFrom(draft: Draft, gateway: Gateway): GatewayPayload {
  const settings: Record<string, unknown> = {};
  for (const field of gateway.settings_fields) {
    const value = draft.settings[field.key];
    if (Array.isArray(value)) {
      if (value.length > 0) settings[field.key] = value;
      continue;
    }
    if (value.trim()) settings[field.key] = value.trim();
  }
  for (const extra of draft.extras) {
    const key = extra.key.trim();
    if (key && extra.value.trim()) settings[key] = extra.value.trim();
  }
  const credentials: Record<string, string> = {};
  for (const [key, value] of Object.entries(draft.credentials)) {
    if (value.trim()) credentials[key] = value.trim();
  }
  return {
    is_enabled: draft.is_enabled,
    mode: draft.mode,
    priority: Number(draft.priority) || 0,
    label: draft.label.trim() || null,
    credentials,
    settings,
  };
}

function ConfigureGateway({
  gateway,
  onClose,
}: {
  gateway: Gateway;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(gateway));
  const save = useSaveGateway();

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function toggleInstrument(fieldKey: string, code: string) {
    setDraft((prev) => {
      const current = Array.isArray(prev.settings[fieldKey]) ? (prev.settings[fieldKey] as string[]) : [];
      const next = current.includes(code) ? current.filter((item) => item !== code) : [...current, code];
      return { ...prev, settings: { ...prev.settings, [fieldKey]: next } };
    });
  }

  return (
    <Modal
      open
      wide
      title={`${gateway.display_label} · ${KIND_LABELS[gateway.kind] ?? gateway.kind}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              save.mutate(
                { provider: gateway.provider, input: payloadFrom(draft, gateway) },
                { onSuccess: onClose },
              )
            }
            disabled={save.isPending}
          >
            {save.isPending ? "Saving…" : "Save gateway"}
          </Button>
        </>
      }
    >
      <ErrorBanner error={save.error} />

      {gateway.status !== "ready" ? (
        <p className="muted">
          {gateway.label} can be configured now, but its checkout adapter has not shipped yet: the
          storefront will not offer it until it does. Stored credentials are kept.
        </p>
      ) : null}

      <Field label="Name at checkout" hint={`Leave empty to use "${gateway.label}"`}>
        <Input value={draft.label} placeholder={gateway.label} onChange={(e) => set("label", e.target.value)} />
      </Field>

      <div className="gateway-fields">
        <Field label="Mode" hint="Test keys take test payments">
          <SheetSelect
            value={draft.mode}
            options={GATEWAY_MODES.map((mode) => ({ value: mode, label: titleCase(mode) }))}
            onChange={(value) => set("mode", value)}
            title="Gateway mode"
          />
        </Field>
        <Field label="Display order" hint="Lower numbers appear first at checkout">
          <Input
            value={draft.priority}
            inputMode="numeric"
            onChange={(e) => set("priority", e.target.value)}
          />
        </Field>
      </div>

      <Field label="Enabled" hint={gateway.status === "ready" ? "Offer this gateway in the storefront checkout" : "Not available until the adapter ships"}>
        <label className="gateway-chip">
          <input
            type="checkbox"
            checked={draft.is_enabled}
            disabled={gateway.status !== "ready"}
            onChange={(e) => set("is_enabled", e.target.checked)}
          />
          {draft.is_enabled ? "Enabled" : "Disabled"}
        </label>
      </Field>

      {gateway.credential_fields.length > 0 ? (
        <>
          <h3 className="section-title">Credentials</h3>
          <p className="muted">
            Secrets are stored per company and never sent back to the browser. Leave a field blank
            to keep the value already saved.
            {gateway.source === "environment" ? " This deployment currently supplies them from the environment." : null}
          </p>
          {gateway.credential_fields.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              hint={[field.help, gateway.credential_keys.includes(field.key) ? "Already saved" : null]
                .filter(Boolean)
                .join(" · ")}
            >
              <Input
                type={field.secret ? "password" : "text"}
                autoComplete="off"
                placeholder={
                  gateway.credential_keys.includes(field.key)
                    ? "•••••••• saved"
                    : field.placeholder ?? (field.required ? "Required" : "Optional")
                }
                value={draft.credentials[field.key] ?? ""}
                onChange={(e) => set("credentials", { ...draft.credentials, [field.key]: e.target.value })}
              />
            </Field>
          ))}
        </>
      ) : null}

      <h3 className="section-title">Checkout options</h3>
      {gateway.settings_fields.map((field) => {
        const value = draft.settings[field.key];
        if (field.type === "multi_select") {
          const selected = Array.isArray(value) ? value : [];
          return (
            <Field key={field.key} label={field.label} hint={field.help}>
              <div className="gateway-instruments">
                {(field.options ?? []).map((option) => (
                  <label key={option.value} className={`gateway-chip ${selected.includes(option.value) ? "on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={selected.includes(option.value)}
                      onChange={() => toggleInstrument(field.key, option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </Field>
          );
        }
        if (field.type === "textarea") {
          return (
            <Field key={field.key} label={field.label} hint={field.help}>
              <Textarea
                rows={2}
                value={stringValue(value)}
                onChange={(e) => set("settings", { ...draft.settings, [field.key]: e.target.value })}
              />
            </Field>
          );
        }
        return (
          <Field key={field.key} label={field.label} hint={field.help}>
            <Input
              inputMode={field.type === "money" ? "decimal" : undefined}
              placeholder={field.type === "money" ? "No limit" : undefined}
              value={stringValue(value)}
              onChange={(e) => set("settings", { ...draft.settings, [field.key]: e.target.value })}
            />
          </Field>
        );
      })}

      <h3 className="section-title">Custom settings</h3>
      <p className="muted">
        Any extra key/value this gateway needs. They are stored with the gateway and returned to
        whichever integration reads the configuration.
      </p>
      {draft.extras.map((extra, index) => (
        <div className="gateway-extra" key={index}>
          <Input
            value={extra.key}
            placeholder="setting_name"
            onChange={(e) => {
              const next = [...draft.extras];
              next[index] = { ...extra, key: e.target.value };
              set("extras", next);
            }}
          />
          <Input
            value={extra.value}
            placeholder="value"
            onChange={(e) => {
              const next = [...draft.extras];
              next[index] = { ...extra, value: e.target.value };
              set("extras", next);
            }}
          />
          <Button
            variant="secondary"
            onClick={() => set("extras", draft.extras.filter((_, i) => i !== index))}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button variant="secondary" onClick={() => set("extras", [...draft.extras, { key: "", value: "" }])}>
        Add setting
      </Button>
    </Modal>
  );
}

export function GatewaysPage() {
  const { has } = usePermissions();
  const canManage = has("payments.gateways.manage");
  const gateways = useQuery(gatewaysQueryOptions());
  const save = useSaveGateway();
  const remove = useDeleteGateway();

  const [editing, setEditing] = useState<Gateway | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  if (gateways.isLoading) return <Spinner />;
  if (gateways.isError) return <ErrorBanner error={gateways.error} />;

  const rows = gateways.data?.gateways ?? [];

  return (
    <>
      <PageHeader
        title="Payment gateways"
        description="Enable one or several gateways per company and customise what the storefront checkout offers"
      />

      <ErrorBanner error={save.error ?? remove.error} />

      <div className="gateway-grid">
        {rows.map((gateway) => {
          const enabled = gateway.is_enabled;
          return (
            <Card key={gateway.provider}>
              <div className="gateway-head">
                <div>
                  <strong>{gateway.display_label}</strong>
                  <div className="muted">
                    {gateway.provider} · {KIND_LABELS[gateway.kind] ?? gateway.kind}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {gateway.status === "ready" ? (
                    <StatusBadge status={enabled ? "active" : "inactive"} />
                  ) : (
                    <Badge tone="warn">Coming soon</Badge>
                  )}
                </div>
              </div>

              <div className="muted">
                {enabled ? "Offered at checkout" : "Not offered at checkout"} · order {gateway.priority} ·{" "}
                {titleCase(gateway.mode)}
                {gateway.credential_fields.length > 0
                  ? ` · credentials ${gateway.configured ? `set (${gateway.source})` : "missing"}`
                  : ""}
              </div>

              {Array.isArray(gateway.settings.methods) && gateway.settings.methods.length > 0 ? (
                <div className="muted">
                  Instruments: {(gateway.settings.methods as string[]).map(titleCase).join(", ")}
                </div>
              ) : null}
              {typeof gateway.settings.instructions === "string" && gateway.settings.instructions ? (
                <div className="muted">Checkout note: “{gateway.settings.instructions}”</div>
              ) : null}
              {Object.entries(gateway.settings)
                .filter(([key]) => !["methods", "instructions", "min_order", "max_order"].includes(key))
                .map(([key, value]) => (
                  <div className="muted" key={key}>
                    {key}: {stringValue(value)}
                  </div>
                ))}

              <div className="gateway-actions">
                {canManage ? (
                  <>
                    <Button variant="secondary" onClick={() => setEditing(gateway)}>
                      Configure
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={save.isPending || (!enabled && !gateway.configured && gateway.credential_fields.length > 0)}
                      title={
                        !enabled && !gateway.configured && gateway.credential_fields.length > 0
                          ? "Add credentials first"
                          : undefined
                      }
                      onClick={() =>
                        save.mutate({ provider: gateway.provider, input: { is_enabled: !enabled } })
                      }
                    >
                      {enabled ? "Disable" : "Enable"}
                    </Button>
                    {gateway.source === "company" ||
                    Object.keys(gateway.settings).length > 0 ||
                    enabled ? (
                      confirmRemove === gateway.provider ? (
                        <>
                          <Button
                            variant="secondary"
                            onClick={() => remove.mutate(gateway.provider, { onSuccess: () => setConfirmRemove(null) })}
                            disabled={remove.isPending}
                          >
                            Confirm remove
                          </Button>
                          <Button variant="secondary" onClick={() => setConfirmRemove(null)}>
                            Keep
                          </Button>
                        </>
                      ) : (
                        <Button variant="secondary" onClick={() => setConfirmRemove(gateway.provider)}>
                          Remove
                        </Button>
                      )
                    ) : null}
                  </>
                ) : (
                  <span className="muted">Read-only</span>
                )}
                {gateway.docs_url ? (
                  <a className="shop-text-link" href={gateway.docs_url} target="_blank" rel="noreferrer">
                    Docs
                  </a>
                ) : null}
              </div>
            </Card>
          );
        })}
      </div>

      {rows.length === 0 ? (
        <Card>
          <div className="empty">
            <div className="empty-title">No gateways available</div>
          </div>
        </Card>
      ) : null}

      {editing ? (
        <ConfigureGateway
          gateway={rows.find((row) => row.provider === editing.provider) ?? editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}
