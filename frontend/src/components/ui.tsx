import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
} from "react";
import { errorMessage } from "../lib/api-client";
import { type Tone, statusTone } from "../lib/format";
import { cn } from "../lib/utils";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="topbar">
      <div>
        <h1 className="page-title" style={{ marginBottom: 2 }}>
          {title}
        </h1>
        {description ? (
          <p className="muted" style={{ margin: 0 }}>
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="toolbar">{actions}</div> : null}
    </div>
  );
}

export function Card({
  children,
  className,
  title,
  actions,
}: {
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className={cn("card", className)}>
      {title || actions ? (
        <div className="card-head">
          <div className="card-title">{title}</div>
          {actions ? <div className="toolbar">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

export function Button({
  variant = "primary",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button type={type} className={cn(variant !== "primary" && variant, className)} {...props} />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={className} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={className} {...props} />;
}

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label?: ReactNode;
  error?: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="field">
      {label ? <label>{label}</label> : null}
      {children}
      {error ? <div className="error-text">{error}</div> : hint ? <div className="muted">{hint}</div> : null}
    </div>
  );
}

export function Badge({ tone = "default", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("badge", tone !== "default" && tone)}>{children}</span>;
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  return <Badge tone={statusTone(status)}>{status ? status.replace(/_/g, " ") : "—"}</Badge>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="muted" style={{ padding: 12 }}>
      {label}
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  message,
  action,
}: {
  title?: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-title">{title}</div>
      {message ? <div className="muted">{message}</div> : null}
      {action ? <div style={{ marginTop: 10 }}>{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="empty">
      <div className="empty-title error-text">{errorMessage(error)}</div>
      {onRetry ? (
        <Button variant="secondary" style={{ marginTop: 10 }} onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="error-banner">{errorMessage(error)}</div>;
}

export function Kpi({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="kpi">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
      {hint ? <div className="muted">{hint}</div> : null}
    </div>
  );
}

export function KpiRow({ children }: { children: ReactNode }) {
  return <div className="kpi-row">{children}</div>;
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={cn("modal", wide && "wide")} onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <h2 className="modal-title">{title}</h2>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="tabs">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={cn("tab", tab.key === active && "active")}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export interface Column<T> {
  key: string;
  header: ReactNode;
  render?: (row: T, index: number) => ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  error,
  onRetry,
  empty,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T, index: number) => string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: ReactNode;
}) {
  if (loading) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!rows || rows.length === 0) return <>{empty ?? <EmptyState />}</>;
  return (
    <table className="data">
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column.key} style={column.align ? { textAlign: column.align } : undefined}>
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={rowKey(row, index)}>
            {columns.map((column) => (
              <td
                key={column.key}
                className={column.className}
                style={column.align ? { textAlign: column.align } : undefined}
              >
                {column.render ? column.render(row, index) : null}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
