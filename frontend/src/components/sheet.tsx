import { useEffect, useMemo, useState, type ReactNode } from "react";
import { cn } from "../lib/utils";
import { Button } from "./ui";

/**
 * Generic slide-over panel. Every picker in the app is a Sheet with a search
 * field (see `SheetSelect`) rather than a native <select>.
 */
export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <aside className="sheet" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header className="sheet-head">
          <h2 className="modal-title">{title}</h2>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </header>
        {children}
        {footer ? <footer className="sheet-foot">{footer}</footer> : null}
      </aside>
    </div>
  );
}

export interface SheetOption {
  value: string;
  label: string;
  hint?: string;
}

export function SheetSelect({
  label,
  value,
  options,
  onChange,
  placeholder = "Select…",
  title,
  searchPlaceholder = "Search…",
  disabled,
  loading,
  emptyText = "No options",
  className,
}: {
  label?: string;
  value: string | null | undefined;
  options: SheetOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  title?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  loading?: boolean;
  emptyText?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (open) setQuery("");
  }, [open]);

  const selected = options.find((option) => option.value === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(q) || (option.hint?.toLowerCase().includes(q) ?? false),
    );
  }, [options, query]);

  return (
    <div className={cn("sheet-select", className)}>
      {label ? (
        <div className="muted" style={{ marginBottom: 4 }}>
          {label}
        </div>
      ) : null}
      <button type="button" className="sheet-trigger" disabled={disabled} onClick={() => setOpen(true)}>
        <span className={selected ? undefined : "placeholder"}>
          {selected ? selected.label : placeholder}
        </span>
        <span className="chevron">▾</span>
      </button>
      <Sheet open={open} title={title ?? label ?? "Select"} onClose={() => setOpen(false)}>
        <div className="sheet-search">
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={searchPlaceholder}
          />
        </div>
        <div className="sheet-list">
          {loading ? (
            <div className="muted" style={{ padding: 12 }}>
              Loading…
            </div>
          ) : null}
          {!loading && filtered.length === 0 ? (
            <div className="muted" style={{ padding: 12 }}>
              {emptyText}
            </div>
          ) : null}
          {filtered.map((option) => (
            <button
              key={option.value}
              type="button"
              className={cn("sheet-option", option.value === value && "selected")}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <span>{option.label}</span>
              {option.hint ? <span className="muted">{option.hint}</span> : null}
            </button>
          ))}
        </div>
      </Sheet>
    </div>
  );
}
