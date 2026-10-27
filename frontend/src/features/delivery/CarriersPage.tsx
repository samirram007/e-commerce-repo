import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { Button, Card, ErrorBanner, Field, Input, Modal, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { Badge } from "../../components/ui";
import { api } from "../../lib/api-client";
import { usePermissions } from "../../hooks/use-permissions";

/**
 * Third-party shipping carriers: enable one or several per company, store their
 * credentials and set the order they are offered in at checkout. The carrier
 * catalog (credential fields, whether the adapter has shipped) comes from
 * `app/modules/delivery/profiles.py`, so this panel needs no per-carrier code.
 */
const credentialFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  secret: z.boolean().optional(),
  required: z.boolean().optional(),
  placeholder: z.string().optional(),
  help: z.string().optional(),
});

const carrierSchema = z.object({
  carrier: z.string(),
  label: z.string(),
  display_label: z.string(),
  kind: z.string(),
  status: z.string(),
  rate_source: z.string(),
  credential_fields: z.array(credentialFieldSchema),
  docs_url: z.string().optional(),
  is_enabled: z.boolean(),
  priority: z.number(),
  credential_keys: z.array(z.string()),
  configured: z.boolean(),
  source: z.string(),
  notes: z.string().nullable().optional(),
});
type Carrier = z.infer<typeof carrierSchema>;

const carriersSchema = z.object({ carriers: z.array(z.unknown()), profiles: z.array(carrierSchema) });

export const carrierKeys = {
  all: ["shipping-carriers"] as const,
  list: () => [...carrierKeys.all, "list"] as const,
};

export function carriersQueryOptions() {
  return {
    queryKey: carrierKeys.list(),
    queryFn: async (): Promise<Carrier[]> => {
      const { data } = await api.get("/delivery/carriers");
      return carriersSchema.parse(data).profiles;
    },
  };
}

function useSaveCarrier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      carrier,
      input,
    }: {
      carrier: string;
      input: { is_enabled?: boolean; priority?: number; label?: string | null; credentials?: Record<string, string> };
    }) => {
      const { data } = await api.put(`/delivery/carriers/${carrier}`, input);
      return carrierSchema.parse(data);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: carrierKeys.all }),
  });
}

function useDeleteCarrier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (carrier: string) => {
      await api.delete(`/delivery/carriers/${carrier}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: carrierKeys.all }),
  });
}

function ConfigureCarrier({ carrier, onClose }: { carrier: Carrier; onClose: () => void }) {
  const save = useSaveCarrier();
  const [label, setLabel] = useState(carrier.display_label === carrier.label ? "" : carrier.display_label);
  const [priority, setPriority] = useState(String(carrier.priority));
  const [enabled, setEnabled] = useState(carrier.is_enabled);
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  return (
    <Modal
      open
      wide
      title={`${carrier.display_label} · ${carrier.rate_source === "api" ? "carrier rate API" : "shop delivery rules"}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button
            disabled={save.isPending}
            onClick={() => {
              const filled: Record<string, string> = {};
              for (const [key, value] of Object.entries(credentials)) {
                if (value.trim()) filled[key] = value.trim();
              }
              save.mutate(
                {
                  carrier: carrier.carrier,
                  input: {
                    is_enabled: enabled,
                    priority: Number(priority) || 0,
                    label: label.trim() || null,
                    credentials: filled,
                  },
                },
                { onSuccess: onClose },
              );
            }}
          >
            {save.isPending ? "Saving…" : "Save carrier"}
          </Button>
        </>
      }
    >
      <ErrorBanner error={save.error} />

      {carrier.status !== "ready" ? (
        <p className="muted">
          {carrier.label} can be configured now, but its dispatch and rate adapter has not shipped
          yet: checkout will not offer it, and rates keep using the shop's delivery rules. Stored
          credentials are kept.
        </p>
      ) : null}

      <Field label="Name at checkout" hint={`Leave empty to use "${carrier.label}"`}>
        <Input value={label} placeholder={carrier.label} onChange={(event) => setLabel(event.target.value)} />
      </Field>
      <Field label="Display order" hint="Lower numbers are offered first at checkout">
        <Input value={priority} inputMode="numeric" onChange={(event) => setPriority(event.target.value)} />
      </Field>
      <Field label="Enabled" hint={carrier.status === "ready" ? "Offer this carrier at checkout" : "Not available until the adapter ships"}>
        <label className="gateway-chip">
          <input
            type="checkbox"
            checked={enabled}
            disabled={carrier.status !== "ready"}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          {enabled ? "Enabled" : "Disabled"}
        </label>
      </Field>

      {carrier.credential_fields.length > 0 ? (
        <>
          <h3 className="section-title">Credentials</h3>
          <p className="muted">
            Secrets are stored per company and never sent back to the browser. Leave a field blank
            to keep the value already saved.
          </p>
          {carrier.credential_fields.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              hint={[field.help, carrier.credential_keys.includes(field.key) ? "Already saved" : null]
                .filter(Boolean)
                .join(" · ")}
            >
              <Input
                type={field.secret ? "password" : "text"}
                autoComplete="off"
                placeholder={
                  carrier.credential_keys.includes(field.key)
                    ? "•••••••• saved"
                    : field.placeholder ?? (field.required ? "Required" : "Optional")
                }
                value={credentials[field.key] ?? ""}
                onChange={(event) =>
                  setCredentials({ ...credentials, [field.key]: event.target.value })
                }
              />
            </Field>
          ))}
        </>
      ) : null}
    </Modal>
  );
}

export function CarriersPage() {
  const { has } = usePermissions();
  const canManage = has("delivery.carriers.manage");
  const carriers = useQuery(carriersQueryOptions());
  const save = useSaveCarrier();
  const remove = useDeleteCarrier();
  const [editing, setEditing] = useState<string | null>(null);

  if (carriers.isLoading) return <Spinner />;
  if (carriers.isError) return <ErrorBanner error={carriers.error} />;

  const rows = carriers.data ?? [];

  return (
    <>
      <PageHeader
        title="Shipping carriers"
        description="Enable one or several carriers per company; checkout offers them in this order and falls back to your delivery rules when a carrier cannot quote"
      />
      <ErrorBanner error={save.error ?? remove.error} />

      <div className="gateway-grid">
        {rows.map((carrier) => (
          <Card key={carrier.carrier}>
            <div className="gateway-head">
              <div>
                <strong>{carrier.display_label}</strong>
                <div className="muted">
                  {carrier.carrier} ·{" "}
                  {carrier.kind === "api" ? "third-party API" : "own delivery"}
                </div>
              </div>
              {carrier.status === "ready" ? (
                <StatusBadge status={carrier.is_enabled ? "active" : "inactive"} />
              ) : (
                <Badge tone="warn">Adapter pending</Badge>
              )}
            </div>

            <div className="muted">
              {carrier.is_enabled ? "Offered at checkout" : "Not offered at checkout"} · order{" "}
              {carrier.priority} · rates from{" "}
              {carrier.rate_source === "api" ? "the carrier (rules as fallback)" : "your delivery rules"}
              {carrier.credential_fields.length > 0
                ? ` · credentials ${carrier.configured ? `set (${carrier.source})` : "missing"}`
                : ""}
            </div>

            <div className="gateway-actions">
              {canManage ? (
                <>
                  <Button variant="secondary" onClick={() => setEditing(carrier.carrier)}>
                    Configure
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={save.isPending || (!carrier.is_enabled && !carrier.configured)}
                    title={
                      !carrier.is_enabled && !carrier.configured ? "Add credentials first" : undefined
                    }
                    onClick={() =>
                      save.mutate({
                        carrier: carrier.carrier,
                        input: { is_enabled: !carrier.is_enabled },
                      })
                    }
                  >
                    {carrier.is_enabled ? "Disable" : "Enable"}
                  </Button>
                  {carrier.source === "company" || carrier.is_enabled ? (
                    <Button
                      variant="secondary"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(carrier.carrier)}
                    >
                      Remove
                    </Button>
                  ) : null}
                </>
              ) : (
                <span className="muted">Read-only</span>
              )}
              {carrier.docs_url ? (
                <a className="shop-text-link" href={carrier.docs_url} target="_blank" rel="noreferrer">
                  Docs
                </a>
              ) : null}
            </div>
          </Card>
        ))}
      </div>

      {editing ? (
        <ConfigureCarrier
          carrier={rows.find((row) => row.carrier === editing) ?? rows[0]}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}
