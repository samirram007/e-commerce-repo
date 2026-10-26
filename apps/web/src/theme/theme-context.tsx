/**
 * Theme context: exposes the signed-in user's look-and-feel preferences and
 * persists them (localStorage instantly; the backend opportunistically).
 *
 * The store (`theme-store.ts`) owns state so it can apply pre-paint; this
 * provider only wires React to it and keeps the backend copy in sync.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { api } from "../lib/api-client";
import {
  applyThemeDocument,
  getThemeState,
  isDensity,
  isHexColor,
  isThemeMode,
  resolveMode,
  resetThemeState,
  setThemeState,
  subscribeTheme,
  type Density,
  type ThemeMode,
} from "./theme-store";

interface ThemeContextValue {
  theme: ThemeMode;
  accentColor: string;
  density: Density;
  /** Effective mode after resolving "system". */
  resolvedMode: "light" | "dark";
  setTheme: (theme: ThemeMode) => void;
  setAccentColor: (color: string) => void;
  setDensity: (density: Density) => void;
  /** Rotate light → dark → system (used by the quick topbar toggle). */
  cycleTheme: () => void;
  reset: () => void;
  /** Load preferences from the backend once a session exists. */
  syncFromServer: () => Promise<void>;
  /** Push the current preferences to the backend (fire-and-forget). */
  syncToServer: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ServerPreferences {
  theme?: string;
  accent_color?: string;
  density?: string;
}

export function ThemeProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const state = useSyncExternalStore(
    subscribeTheme,
    getThemeState,
    () => getThemeState(),
  );

  const syncFromServer = useCallback(async () => {
    try {
      const { data } = await api.get<ServerPreferences>("/auth/preferences");
      // Only adopt server values the client considers valid (defensive).
      setThemeState({
        theme: isThemeMode(data.theme) ? data.theme : undefined,
        accentColor: isHexColor(data.accent_color) ? data.accent_color : "",
        density: isDensity(data.density) ? data.density : undefined,
      });
    } catch {
      // Offline / unauthenticated — local state stands.
    }
  }, []);

  const syncToServer = useCallback(() => {
    const current = getThemeState();
    void api
      .put("/auth/preferences", {
        theme: current.theme,
        accent_color: current.accentColor,
        density: current.density,
      })
      .catch(() => undefined); // non-critical: localStorage still holds it
  }, []);

  const setTheme = useCallback(
    (theme: ThemeMode) => {
      setThemeState({ theme });
      syncToServer();
    },
    [syncToServer],
  );

  const setAccentColor = useCallback(
    (accentColor: string) => {
      setThemeState({ accentColor });
      syncToServer();
    },
    [syncToServer],
  );

  const setDensity = useCallback(
    (density: Density) => {
      setThemeState({ density });
      syncToServer();
    },
    [syncToServer],
  );

  const cycleTheme = useCallback(() => {
    const order: ThemeMode[] = ["light", "dark", "system"];
    const next = order[(order.indexOf(getThemeState().theme) + 1) % order.length];
    setThemeState({ theme: next });
    syncToServer();
  }, [syncToServer]);

  const reset = useCallback(() => {
    resetThemeState();
    syncToServer();
  }, [syncToServer]);

  // Keep the document in sync when not changed through the store (e.g. OS flip).
  useEffect(() => {
    applyThemeDocument(state);
  }, [state]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme: state.theme,
      accentColor: state.accentColor,
      density: state.density,
      resolvedMode: resolveMode(state.theme),
      setTheme,
      setAccentColor,
      setDensity,
      cycleTheme,
      reset,
      syncFromServer,
      syncToServer,
    }),
    [state, setTheme, setAccentColor, setDensity, cycleTheme, reset, syncFromServer, syncToServer],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>");
  return ctx;
}
