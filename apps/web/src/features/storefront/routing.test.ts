import { describe, expect, it } from "vitest";
import { shopSignInHref } from "./routing";

describe("shopSignInHref", () => {
  it("returns the shopper to the current shop page after signing in", () => {
    expect(shopSignInHref("/cart")).toBe("/login?redirect=%2Fcart");
  });

  it("encodes search strings so filters survive the round trip", () => {
    const href = shopSignInHref("/shop?category=abc&q=red shoes");

    expect(href.startsWith("/login?redirect=")).toBe(true);
    const redirect = new URL(href, "https://store.test").searchParams.get("redirect");
    expect(redirect).toBe("/shop?category=abc&q=red shoes");
  });

  it("falls back to the storefront for a non-path href", () => {
    expect(shopSignInHref("shop/cart")).toBe("/login?redirect=%2Fshop");
    expect(shopSignInHref("")).toBe("/login?redirect=%2Fshop");
  });
});
