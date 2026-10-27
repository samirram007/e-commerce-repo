import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { Button, Card, ErrorBanner, Field, Input, Spinner, Textarea } from "../../components/ui";
import { api } from "../../lib/api-client";
import { usePermissions } from "../../hooks/use-permissions";

/**
 * Storefront tab: the shop's shipping/return rules and its policy pages.
 *
 * The Return Policy lives here too — it is what the storefront shows at
 * `/policies/returns` and links from the shopper's orders page, and the return
 * window below is what the return request is measured against.
 */
const settingsSchema = z.object({
  free_shipping_threshold: z.string().nullable(),
  flat_shipping_fee: z.string().nullable(),
  return_window_days: z.number(),
  contact_phone: z.string().nullable(),
  contact_email: z.string().nullable(),
  contact_address: z.string().nullable(),
  announcements: z.array(z.string()),
  perks: z.array(z.unknown()),
  about_values: z.array(z.unknown()),
  about_stats: z.array(z.unknown()),
  footer_about: z.string().nullable(),
});
type StoreSettings = z.infer<typeof settingsSchema>;

const sectionSchema = z.object({ heading: z.string(), body: z.string() });

const policySchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  updated: z.string(),
  sections: z.array(sectionSchema),
  sort_order: z.number(),
  is_active: z.boolean(),
});
type Policy = z.infer<typeof policySchema>;

const storefrontKeys = {
  settings: ["storefront-admin", "settings"] as const,
  policies: ["storefront-admin", "policies"] as const,
};

/** Sections a fresh Return Policy starts from (the store edits them freely). */
const RETURN_POLICY_DRAFT: Policy = {
  id: "",
  slug: "returns",
  title: "Return Policy",
  updated: "",
  sections: [
    { heading: "Returns window", body: "Returns can be requested within the window shown on your order page, counted from delivery." },
    { heading: "Condition", body: "Items must be unused and in their original packaging with the tags intact." },
    { heading: "How to request", body: "Open your orders page, choose Return items, and pick the quantities you are sending back." },
    { heading: "Refunds", body: "Once the return is approved and received, the refund is issued to your original payment method." },
  ],
  sort_order: 0,
  is_active: true,
};

function PolicyEditor({
  policy,
  onClose,
}: {
  policy: Policy;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Policy>(policy);
  const [error, setError] = useState<unknown>(null);
  const creating = policy.id === "";

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        slug: draft.slug,
        title: draft.title,
        updated: draft.updated,
        sections: draft.sections.filter((section) => section.heading || section.body),
        sort_order: draft.sort_order,
        is_active: draft.is_active,
      };
      const { data } = creating
        ? await api.post("/storefront/admin/policies", body)
        : await api.patch(`/storefront/admin/policies/${policy.id}`, body);
      return policySchema.parse(data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: storefrontKeys.policies });
      onClose();
    },
    onError: (cause) => setError(cause),
  });

  function setSection(index: number, patch: Partial<{ heading: string; body: string }>) {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((section, i) => (i === index ? { ...section, ...patch } : section)),
    }));
  }

  return (
    <div className="stack">
      <ErrorBanner error={error} />
      <div className="gateway-fields">
        <Field label="Title">
          <Input
            value={draft.title}
            onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
          />
        </Field>
        <Field label="Slug" hint="The page URL: /policies/<slug>">
          <Input
            value={draft.slug}
            disabled={!creating}
            onChange={(event) => setDraft((prev) => ({ ...prev, slug: event.target.value }))}
          />
        </Field>
        <Field label="Last updated" hint="Shown as written, e.g. October 2026">
          <Input
            value={draft.updated}
            onChange={(event) => setDraft((prev) => ({ ...prev, updated: event.target.value }))}
          />
        </Field>
        <Field label="Sort order">
          <Input
            value={String(draft.sort_order)}
            inputMode="numeric"
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, sort_order: Number(event.target.value) || 0 }))
            }
          />
        </Field>
      </div>

      <h3 className="section-title">Sections</h3>
      {draft.sections.map((section, index) => (
        <div key={index} className="stack">
          <Field label={`Section ${index + 1} heading`}>
            <Input
              value={section.heading}
              onChange={(event) => setSection(index, { heading: event.target.value })}
            />
          </Field>
          <Field label="Text">
            <Textarea
              rows={3}
              value={section.body}
              onChange={(event) => setSection(index, { body: event.target.value })}
            />
          </Field>
          <Button
            variant="secondary"
            onClick={() =>
              setDraft((prev) => ({
                ...prev,
                sections: prev.sections.filter((_, i) => i !== index),
              }))
            }
          >
            Remove section
          </Button>
        </div>
      ))}
      <Button
        variant="secondary"
        onClick={() =>
          setDraft((prev) => ({ ...prev, sections: [...prev.sections, { heading: "", body: "" }] }))
        }
      >
        Add section
      </Button>

      <label className="gateway-chip">
        <input
          type="checkbox"
          checked={draft.is_active}
          onChange={(event) => setDraft((prev) => ({ ...prev, is_active: event.target.checked }))}
        />
        Published on the storefront
      </label>

      <div className="gateway-actions">
        <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
          Cancel
        </Button>
        <Button onClick={() => save.mutate()} disabled={save.isPending || !draft.title.trim()}>
          {save.isPending ? "Saving…" : creating ? "Create policy" : "Save policy"}
        </Button>
      </div>
    </div>
  );
}

export function StorefrontTab() {
  const { has } = usePermissions();
  const canManage = has("storefront.manage");
  const qc = useQueryClient();

  const settings = useQuery({
    queryKey: storefrontKeys.settings,
    queryFn: async (): Promise<StoreSettings> => {
      const { data } = await api.get("/storefront/admin/settings");
      return settingsSchema.parse(data);
    },
  });
  const policies = useQuery({
    queryKey: storefrontKeys.policies,
    queryFn: async (): Promise<Policy[]> => {
      const { data } = await api.get("/storefront/admin/policies");
      return z.array(policySchema).parse(data);
    },
  });

  const [form, setForm] = useState({
    free_shipping_threshold: "",
    flat_shipping_fee: "",
    return_window_days: "7",
  });
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState<Policy | null>(null);

  useEffect(() => {
    if (!settings.data) return;
    setForm({
      free_shipping_threshold: settings.data.free_shipping_threshold ?? "",
      flat_shipping_fee: settings.data.flat_shipping_fee ?? "",
      return_window_days: String(settings.data.return_window_days ?? 7),
    });
  }, [settings.data]);

  const saveSettings = useMutation({
    // PUT replaces the whole settings object, so the untouched fields go back as-is.
    mutationFn: async () => {
      const current = settings.data;
      const { data } = await api.put("/storefront/admin/settings", {
        ...current,
        free_shipping_threshold: form.free_shipping_threshold.trim() || null,
        flat_shipping_fee: form.flat_shipping_fee.trim() || null,
        return_window_days: Math.max(0, Math.min(365, Number(form.return_window_days) || 0)),
      });
      return settingsSchema.parse(data);
    },
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: storefrontKeys.settings });
    },
    onError: (cause) => setError(cause),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/storefront/admin/policies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: storefrontKeys.policies }),
  });

  if (settings.isLoading || policies.isLoading) return <Spinner />;
  if (settings.isError) return <ErrorBanner error={settings.error} />;

  const rows = policies.data ?? [];
  const hasReturnPolicy = rows.some((policy) => policy.slug === "returns");

  return (
    <>
      <ErrorBanner error={error ?? remove.error} />

      <Card title="Shipping & returns rules">
        <div className="gateway-fields">
          <Field label="Free shipping over" hint="Leave empty to charge shipping on every order">
            <Input
              value={form.free_shipping_threshold}
              inputMode="decimal"
              placeholder="No threshold"
              onChange={(event) =>
                setForm((prev) => ({ ...prev, free_shipping_threshold: event.target.value }))
              }
            />
          </Field>
          <Field label="Flat shipping fee" hint="Charged below the threshold">
            <Input
              value={form.flat_shipping_fee}
              inputMode="decimal"
              placeholder="0"
              onChange={(event) =>
                setForm((prev) => ({ ...prev, flat_shipping_fee: event.target.value }))
              }
            />
          </Field>
          <Field
            label="Return window (days)"
            hint="Counted from delivery; 0 accepts returns any time"
          >
            <Input
              value={form.return_window_days}
              inputMode="numeric"
              onChange={(event) =>
                setForm((prev) => ({ ...prev, return_window_days: event.target.value }))
              }
            />
          </Field>
        </div>
        {canManage ? (
          <div className="gateway-actions">
            <Button onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
              {saveSettings.isPending ? "Saving…" : "Save rules"}
            </Button>
          </div>
        ) : null}
      </Card>

      <Card title="Policy pages">
        <p className="muted">
          Shown to shoppers at <code>/policies/&lt;slug&gt;</code>; the Return Policy is linked from
          their orders page and describes the window set above.
        </p>
        {rows.length === 0 ? (
          <p className="muted">No policy pages yet.</p>
        ) : (
          <div className="stack">
            {rows.map((policy) => (
              <div key={policy.id} className="gateway-head">
                <div>
                  <strong>{policy.title}</strong>
                  <div className="muted">
                    /policies/{policy.slug}
                    {policy.updated ? ` · updated ${policy.updated}` : ""} ·{" "}
                    {policy.sections.length} section{policy.sections.length === 1 ? "" : "s"}
                    {policy.is_active ? "" : " · hidden"}
                  </div>
                </div>
                {canManage ? (
                  <div className="gateway-actions" style={{ marginTop: 0 }}>
                    <Button variant="secondary" onClick={() => setEditing(policy)}>
                      Edit
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(policy.id)}
                    >
                      Delete
                    </Button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
        {canManage ? (
          <div className="gateway-actions">
            <Button variant="secondary" onClick={() => setEditing({ ...RETURN_POLICY_DRAFT })}>
              {hasReturnPolicy ? "New policy" : "Add return policy"}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                setEditing({
                  ...RETURN_POLICY_DRAFT,
                  slug: "",
                  title: "",
                  sections: [{ heading: "", body: "" }],
                })
              }
            >
              New policy
            </Button>
          </div>
        ) : null}
      </Card>

      {editing ? (
        <Card title={editing.id ? `Edit ${editing.title}` : "New policy"}>
          <PolicyEditor policy={editing} onClose={() => setEditing(null)} />
        </Card>
      ) : null}
    </>
  );
}
