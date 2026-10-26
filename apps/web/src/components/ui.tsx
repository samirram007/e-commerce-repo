import {
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
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
  pageSize = 10,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T, index: number) => string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: ReactNode;
  /** Client-side page size. Set 0 to render every row without pagination. */
  pageSize?: number;
}) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(pageSize > 0 ? pageSize : 10);

  // A shrinking result set (new search/filter) snaps back to the first page.
  useEffect(() => {
    setPage(1);
  }, [rows?.length]);

  if (loading) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!rows || rows.length === 0) return <>{empty ?? <EmptyState />}</>;

  const pageCount = Math.max(1, Math.ceil(rows.length / size));
  const current = Math.min(page, pageCount);
  const paginated = pageSize > 0 && rows.length > size;
  // Keep the footer once the user picks a non-default size, so the Rows
  // control never disappears while rows still fit on a single page.
  const showFooter = pageSize > 0 && (paginated || size !== pageSize);
  const start = paginated ? (current - 1) * size : 0;
  const visible = paginated ? rows.slice(start, start + size) : rows;

  return (
    <>
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
          {visible.map((row, index) => (
            <tr key={rowKey(row, start + index)}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={column.className}
                  style={column.align ? { textAlign: column.align } : undefined}
                >
                  {column.render ? column.render(row, start + index) : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {showFooter ? (
        <TablePagination
          from={start + 1}
          to={Math.min(start + size, rows.length)}
          total={rows.length}
          page={current}
          pageCount={pageCount}
          pageSize={size}
          onPageChange={setPage}
          onPageSizeChange={(next) => {
            setSize(next);
            setPage(1);
          }}
        />
      ) : null}
    </>
  );
}

export const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

/** Shared pagination footer: row count, rows-per-page and prev/next controls. */
export function TablePagination({
  from,
  to,
  total,
  page,
  pageCount,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = TABLE_PAGE_SIZE_OPTIONS,
}: {
  from: number;
  to: number;
  /** Omit for unpaginated sources; the label then falls back to `to` rows. */
  total?: number;
  page: number;
  pageCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  pageSizeOptions?: number[];
}) {
  return (
    <div className="table-foot">
      <span className="muted">
        {total === undefined ? `${to} rows` : `${from}–${to} of ${total} rows`}
      </span>
      <div className="toolbar">
        <label className="muted" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          Rows
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            aria-label="Rows per page"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          ← Prev
        </Button>
        <span className="muted">
          Page {page} of {pageCount}
        </span>
        <Button
          variant="secondary"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next →
        </Button>
      </div>
    </div>
  );
}
