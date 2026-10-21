import { useCallback, useMemo, useState, type ReactNode } from "react";
import type { z } from "zod";
import { fieldErrors } from "../lib/zod-utils";
import { ErrorBanner, Field, Input, Modal, Button } from "./ui";
import { SheetSelect, type SheetOption } from "./sheet";

/** 
 * Global base form for CRUD screens.
 * 
 * Values are controlled strings (money/decimal inputs arrive from the API as
 * decimal strings — see `shared/money.py`), validation is a zod schema parsed
 * on submit, and backend field errors can be merged in via `setApiErrors`.
 * Follows the existing PartnersPage pattern (controlled state + zod), not
 * react-hook-form, to stay consistent with the codebase.
 */
export function useCrudForm<TSchema extends z.ZodTypeAny>({
  schema,
  initialValues,
  onSubmit,
}: {
  schema: TSchema;
  initialValues: z.input<TSchema>;
  /** Called with the parsed (output) values when validation succeeds. */
  onSubmit: (values: z.output<TSchema>) => void;
}) {
  const [values, setValues] = useState<z.input<TSchema>>(initialValues);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const setValue = useCallback(<K extends keyof z.input<TSchema>>(
    key: K,
    value: z.input<TSchema>[K],
  ) => {
    setValues(
      (prev) =>
        ({ ...(prev as unknown as Record<string, unknown>), [key]: value }) as z.input<TSchema>,
    );
    setErrors((prev) => (prev[key as string] ? { ...prev, [key as string]: "" } : prev));
  }, []);

  const reset = useCallback(
    (next?: z.input<TSchema>) => {
      setValues(next ?? initialValues);
      setErrors({});
    },
    [initialValues],
  );

  /** Merge normalized backend errors (e.g. from ApiError.details) into the form. */
  const setApiErrors = useCallback(
    (next: Record<string, string>) => {
      setErrors((prev) => ({ ...prev, ...next }));
    },
    [],
  );

  const submit = useCallback(() => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    onSubmit(parsed.data);
  }, [schema, values, onSubmit]);

  return useMemo(
    () => ({ values, errors, setValue, reset, setApiErrors, submit }),
    [values, errors, setValue, reset, setApiErrors, submit],
  );
}

/** Structural shape `CrudFormModal` needs; any `useCrudForm` instance fits. */
export interface CrudFormLike {
  values: Record<string, unknown>;
  errors: Record<string, string>;
  /** Optional legacy hook-owned pending flag; prefer the modal's `submitting` prop. */
  submitting?: boolean;
  setValue(key: never, value: never): void;
  submit(): void;
}

/** Form field specification for `CrudFormModal`. */
export interface FormFieldSpec {
  name: string;
  label: string;
  type?: "text" | "number" | "money" | "select" | "checkbox";
  options?: SheetOption[];
  placeholder?: string;
  disabled?: boolean;
  hint?: string;
  /** Render a custom control instead of the built-in input. */
  render?: (props: {
    value: unknown;
    error: string | undefined;
    setValue: (name: string, value: unknown) => void;
  }) => ReactNode;
}

/**
 * Modal wrapper rendering a form field list from a spec array. Errors come
 * from `useCrudForm`; footer is Cancel + a submit button wired to `form.submit`.
 */
export function CrudFormModal({
  open,
  title,
  form,
  fields,
  onClose,
  onSubmit,
  submitting,
  error,
  wide,
  submitLabel = "Save",
  extra,
}: {
  open: boolean;
  title: ReactNode;
  form: CrudFormLike;
  fields: FormFieldSpec[];
  onClose: () => void;
  /** Outer async submit; receives no args — read the parsed values from the form hook's onSubmit. */
  onSubmit: () => void;
  submitting?: boolean;
  error?: unknown;
  wide?: boolean;
  submitLabel?: string;
  /** Extra content rendered above the footer (e.g. custom fields). */
  extra?: ReactNode;
}) {
  const busy = submitting ?? form.submitting ?? false;
  const formValues = form.values;

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      wide={wide}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={busy}>
            {busy ? "Saving…" : submitLabel}
          </Button>
        </>
      }>
      <ErrorBanner error={error} />
      {fields.map((field) => {
        const value = formValues[field.name];
        const error = form.errors[field.name];
        if (field.render) {
          return (
            <Field key={field.name} label={field.label} error={error} hint={field.hint}>
              {field.render({ value, error, setValue: (name, v) => form.setValue(name as never, v as never) })}
            </Field>
          );
        }
        if (field.type === "checkbox") {
          return (
            <Field key={field.name} label={field.label} error={error} hint={field.hint}>
              <label className="pill">
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  disabled={field.disabled}
                  onChange={(event) => form.setValue(field.name as never, event.target.checked as never)}
                />
                {field.placeholder ?? field.label}
              </label>
            </Field>
          );
        }
        if (field.type === "select") {
          return (
            <Field key={field.name} label={field.label} error={error} hint={field.hint}>
              <SheetSelect
                value={typeof value === "string" ? value : ""}
                options={field.options ?? []}
                onChange={(next) => form.setValue(field.name as never, next as never)}
                disabled={field.disabled}
                placeholder={field.placeholder}
                title={field.label}
              />
            </Field>
          );
        }
        return (
          <Field key={field.name} label={field.label} error={error} hint={field.hint}>
            <Input
              type={field.type === "money" || field.type === "number" ? "text" : "text"}
              inputMode={field.type === "money" || field.type === "number" ? "decimal" : undefined}
              value={
                typeof value === "string" || typeof value === "number" ? String(value) : ""
              }
              disabled={field.disabled}
              onChange={(event) => form.setValue(field.name as never, event.target.value as never)}
            />
          </Field>
        );
      })}
      {extra}
    </Modal>
  );
}