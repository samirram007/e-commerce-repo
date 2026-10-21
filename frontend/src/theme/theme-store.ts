/**
 * Theme store: useSyncExternalStore singleton (same pattern as session-store)
 * holding the signed-in user's look-and-feel choices.
 *
 * Values are persisted to localStorage so they apply before the first paint on
 * reload, and optionally synced to the backend (`PUT /auth/preferences`) so
 * they follow the user across devices. The store never validates the backend
 * response shape beyond light field checks.
 */

export const THEME_OPTIONS = ["light", "dark", "system"] as const;
export type ThemeMode = (typeof THEME_OPTIONS)[number];

export const DENSITY_OPTIONS = ["compact", "comfortable"] as const;
export type Density = (typeof DENSITY_OPTIONS)[number];

/** Curated accent palette; a custom hex may also be set. */
export const ACCENT_SWATCHES: { value: string; label: string }[] = [
  { value: "#2f54eb", label: "Blue" },
  { value: "#1677ff", label: "Sky" },
  { value: "#13c2c2", label: "Teal" },
  { value: "#157347", label: "Green" },
  { value: "#722ed1", label: "Violet" },
  { value: "#d93025", label: "Red" },
  { value: "#a05c00", label: "Amber" },
];

export interface ThemeState {
  theme: ThemeMode;
  accentColor: string;
  density: Density;
}

const STORAGE_KEY = "erp.theme";

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

const DEFAULT_STATE: ThemeState = {
  theme: "system",
  accentColor: "",
  density: "comfortable",
};

function initialState(): ThemeState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw) as Partial<ThemeState>;
    return {
      theme: isThemeMode(parsed.theme) ? parsed.theme : DEFAULT_STATE.theme,
      accentColor: isHexColor(parsed.accentColor) ? parsed.accentColor : DEFAULT_STATE.accentColor,
      density: isDensity(parsed.density) ? parsed.density : DEFAULT_STATE.density,
    };
  } catch {
    return DEFAULT_STATE;
  }
}

export function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && (THEME_OPTIONS as readonly unknown[]).includes(value);
}

export function isDensity(value: unknown): value is Density {
  return typeof value === "string" && (DENSITY_OPTIONS as readonly unknown[]).includes(value);
}

export function isHexColor(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

let state: ThemeState = initialState();
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function persist(next: ThemeState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // storage unavailable (private mode) — session-only theme is acceptable
  }
}

/** Write the current state to the document root and subscribe changes. */
export function applyThemeDocument(next: ThemeState): void {
  const root = document.documentElement;
  root.dataset.theme = next.theme;
  // Effective mode for CSS custom-property aware styles: known at render time.
  root.dataset.resolvedTheme = String(resolveMode(next.theme));
  if (next.accentColor) {
    root.style.setProperty("--accent", next.accentColor);
    root.dataset.accent = next.accentColor;
  } else {
    root.style.removeProperty("--accent");
    root.removeAttribute("data-accent");
  }
  root.dataset.density = next.density;
}

/** Resolve "system" against the OS setting. */
export function resolveMode(mode: ThemeMode): "light" | "dark" {
  if (mode !== "system") return mode;
  return window.matchMedia(DARK_MODE_QUERY).matches ? "dark" : "light";
}

export function getThemeState(): ThemeState {
  return state;
}

export function setThemeState(partial: Partial<ThemeState>): ThemeState {
  const next: ThemeState = {
    theme: isThemeMode(partial.theme) ? partial.theme : state.theme,
    accentColor:
      partial.accentColor === undefined ? state.accentColor : partial.accentColor,
    density: isDensity(partial.density) ? partial.density : state.density,
  };
  const changed = JSON.stringify(next) !== JSON.stringify(state);
  state = next;
  applyThemeDocument(state);
  persist(state);
  if (changed) notify();
  return state;
}

export function resetThemeState(): void {
  setThemeState(DEFAULT_STATE);
}

/** React wire-in for useSyncExternalStore. */
export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// Follow OS scheme changes while "system" is active.
try {
  window.matchMedia(DARK_MODE_QUERY).addEventListener("change", () => {
    if (state.theme === "system") applyThemeDocument(state);
  });
} catch {
  // matchMedia listener unsupported — theme falls back to light for system
}

// Apply before React mounts to avoid a flash of the wrong theme.
applyThemeDocument(state);
