import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchStore } from "./api";
import { cachedCompanyId, setCachedCompanyId, STOREFRONT_SLUG } from "./store";
import type { StoreInfo } from "./types";

interface StoreState {
  /** Resolved store (company) — null until the slug has been resolved. */
  store: StoreInfo | null;
  loading: boolean;
  error: unknown;
}

const StoreContext = createContext<StoreState | null>(null);

/**
 * Resolves the storefront once per page load: the public store endpoint maps
 * the slug to a company, and its id is what every shop request is scoped to.
 */
export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StoreState>({ store: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const info = await fetchStore();
        setCachedCompanyId(info.company_id);
        if (!cancelled) setState({ store: info, loading: false, error: null });
      } catch (error) {
        // Fall back to the last known company so the shop still renders.
        const cached = cachedCompanyId();
        if (cancelled) return;
        setState({
          store: cached
            ? {
                company_id: cached,
                slug: STOREFRONT_SLUG,
                name: "Store",
                currency: "INR",
                allow_guest_checkout: true,
              }
            : null,
          loading: false,
          error,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return <StoreContext.Provider value={state}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreState {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used within <StoreProvider>");
  return ctx;
}

/** Currency of the store (falls back to the app default). */
export function useStoreCurrency(): string {
  const { store } = useStore();
  return store?.currency ?? "INR";
}
