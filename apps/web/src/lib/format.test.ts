import { describe, expect, it } from "vitest";
import { formatRate, gstLabel, splitTaxAmount } from "./format";

describe("formatRate", () => {
  it("trims stored decimal padding", () => {
    expect(formatRate("18.0000")).toBe("18");
    expect(formatRate("2.5000")).toBe("2.5");
    expect(formatRate(12)).toBe("12");
    expect(formatRate(undefined)).toBe("0");
  });
});

describe("splitTaxAmount", () => {
  it("splits a GST amount into CGST and SGST halves", () => {
    expect(splitTaxAmount("7.20")).toEqual({ cgst: 3.6, sgst: 3.6 });
  });

  it("keeps the halves adding back to the original when the paise are odd", () => {
    const { cgst, sgst } = splitTaxAmount("2.95");
    expect(cgst).toBe(1.48);
    expect(sgst).toBe(1.47);
    expect(Number((cgst + sgst).toFixed(2))).toBe(2.95);
  });
});

describe("gstLabel", () => {
  it("shows the GST rate with its CGST and SGST halves", () => {
    expect(gstLabel("18.0000")).toBe("GST 18% · CGST 9% + SGST 9%");
    expect(gstLabel("5")).toBe("GST 5% · CGST 2.5% + SGST 2.5%");
    expect(gstLabel(12)).toBe("GST 12% · CGST 6% + SGST 6%");
  });

  it("falls back to a plain label when there is no rate", () => {
    expect(gstLabel("0.0000")).toBe("GST");
    expect(gstLabel(null)).toBe("GST");
    expect(gstLabel(undefined)).toBe("GST");
  });
});
