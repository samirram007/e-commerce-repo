/**
 * Route smoke test for the storefront split.
 *
 * Browsing the shop is public; a shopper's own orders and wishlist are not.
 * Matches are resolved from the real generated route tree, so a route gaining
 * or losing a `beforeLoad` guard fails this test.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./auth/auth-context", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./auth/auth-context")>();
  return { ...actual, ensureSession: vi.fn() };
});

// The root route installs the theme provider and the settings screen reads the
// theme store, which writes to `document` on import. Nothing here renders, so
// stubs keep this test DOM-free.
vi.mock("./theme/theme-context", () => ({
  ThemeProvider: ({ children }: { children: unknown }) => children,
  useTheme: () => ({}),
}));

vi.mock("./theme/theme-store", () => ({
  THEME_OPTIONS: ["light", "dark", "system"],
  DENSITY_OPTIONS: ["compact", "comfortable"],
  ACCENT_SWATCHES: [],
  isThemeMode: () => true,
  isDensity: () => true,
  isHexColor: () => true,
  applyThemeDocument: () => undefined,
  resolveMode: () => "light",
  getThemeState: () => ({ theme: "system", accent: "#4f46e5", density: "comfortable" }),
  setThemeState: () => ({ theme: "system", accent: "#4f46e5", density: "comfortable" }),
  resetThemeState: () => undefined,
  subscribeTheme: () => () => undefined,
}));

import { createMemoryHistory, createRouter, isRedirect } from "@tanstack/react-router";
import { ensureSession } from "./auth/auth-context";
import { routeTree } from "./routeTree.gen";

const session = vi.mocked(ensureSession);

const router = createRouter({
  routeTree,
  history: createMemoryHistory({ initialEntries: ["/"] }),
});

/** Guards ignore their arguments here; the stub only satisfies the signature. */
const guardContext = {} as never;

/** Result of the first guard on `path` that blocks: `null` when there is none. */
async function runGuards(path: string) {
  const [branch] = router.getMatchedRoutes(path);
  for (const route of branch) {
    const beforeLoad = route.options.beforeLoad;
    if (!beforeLoad) continue;
    try {
      await beforeLoad(guardContext);
    } catch (error) {
      if (isRedirect(error)) return error;
      throw error;
    }
  }
  return null;
}

const PUBLIC_PATHS = [
  "/",
  "/shop",
  "/shop/p-aurora-headphones",
  "/cart",
  "/checkout",
  "/about",
  "/faq",
  "/contact",
  "/policies/privacy",
];

const PROTECTED_PATHS = ["/shop/orders", "/shop/wishlist"];

describe("storefront routes", () => {
  beforeEach(() => {
    session.mockReset();
  });

  it.each(PUBLIC_PATHS)("keeps %s public: no guard on the matched chain", async (path) => {
    session.mockResolvedValue(false);

    const [branch, , leaf] = router.getMatchedRoutes(path);
    expect(leaf).toBeDefined();
    expect(branch.length).toBeGreaterThan(0);
    expect(await runGuards(path)).toBeNull();
  });

  it.each(PROTECTED_PATHS)("sends guests from %s to sign in", async (path) => {
    session.mockResolvedValue(false);

    const redirect = await runGuards(path);

    expect(redirect?.options.to).toBe("/login");
    expect(redirect?.options.search).toEqual({ redirect: path });
  });

  it.each(PROTECTED_PATHS)("lets a signed-in shopper open %s", async (path) => {
    session.mockResolvedValue(true);

    expect(await runGuards(path)).toBeNull();
  });
});
