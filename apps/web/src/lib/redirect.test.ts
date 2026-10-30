import { describe, expect, it } from "vitest";
import { safeRedirect, unmatchedPathTarget } from "./redirect";

describe("safeRedirect", () => {
  it("defaults to the app home when no target was given", () => {
    expect(safeRedirect(undefined)).toBe("/dashboard");
    expect(safeRedirect(null)).toBe("/dashboard");
    expect(safeRedirect("")).toBe("/dashboard");
  });

  it("keeps same-origin app paths, including search and hash", () => {
    expect(safeRedirect("/")).toBe("/");
    expect(safeRedirect("/products")).toBe("/products");
    expect(safeRedirect("/shop/cart?from=products#top")).toBe("/shop/cart?from=products#top");
  });

  it("rejects absolute URLs", () => {
    expect(safeRedirect("https://evil.example/phish")).toBe("/dashboard");
    expect(safeRedirect("javascript:alert(1)")).toBe("/dashboard");
    expect(safeRedirect("shop/cart")).toBe("/dashboard");
  });

  it("rejects protocol-relative URLs, including the backslash form browsers accept", () => {
    expect(safeRedirect("//evil.example")).toBe("/dashboard");
    expect(safeRedirect("///evil.example")).toBe("/dashboard");
    expect(safeRedirect("/\\evil.example")).toBe("/dashboard");
  });

  it("rejects targets with whitespace or control characters", () => {
    expect(safeRedirect("/shop cart")).toBe("/dashboard");
    expect(safeRedirect("/shop\nSet-Cookie: x=1")).toBe("/dashboard");
    expect(safeRedirect("/shop\u0000")).toBe("/dashboard");
  });
});

describe("unmatchedPathTarget", () => {
  it("keeps guests on the public storefront", () => {
    expect(unmatchedPathTarget(false)).toBe("/");
  });

  it("returns signed-in users to the app shell", () => {
    expect(unmatchedPathTarget(true)).toBe("/dashboard");
  });
});
