import { z } from "zod";

/** Decimal strings from the API (Pydantic v2 JSON), like partners/schemas.ts. */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const COUPON_KINDS = ["percent", "fixed"] as const;
export type CouponKind = (typeof COUPON_KINDS)[number];

export const COUPON_SCOPES = ["order", "category", "product"] as const;
export type CouponScope = (typeof COUPON_SCOPES)[number];

export const couponSchema = z.object({
  id: z.string(),
  code: z.string(),
  description: z.string().nullable(),
  kind: z.enum(COUPON_KINDS),
  value: decimalString,
  max_discount: decimalString.nullable(),
  min_subtotal: decimalString,
  scope: z.enum(COUPON_SCOPES),
  category_id: z.string().nullable(),
  product_id: z.string().nullable(),
  starts_at: z.string().nullable(),
  ends_at: z.string().nullable(),
  max_redemptions: z.number().nullable(),
  max_per_customer: z.number().nullable(),
  is_active: z.boolean(),
  /** Lifetime usage, which is what the coupon's limits are checked against. */
  redemptions: z.number(),
  redeemed_amount: decimalString,
});
export type Coupon = z.infer<typeof couponSchema>;

/** Paginated envelope from app.shared.pagination.Page. */
export const couponPageSchema = z.object({
  items: z.array(couponSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type CouponPage = z.infer<typeof couponPageSchema>;

export const redemptionSchema = z.object({
  id: z.string(),
  order_id: z.string(),
  code: z.string(),
  customer_key: z.string().nullable(),
  amount: decimalString,
  redeemed_at: z.string().nullable(),
});
export type CouponRedemption = z.infer<typeof redemptionSchema>;

/**
 * Form values are the raw strings the inputs hold. The transform below turns
 * them into the API payload: empty optional fields become null so a coupon can
 * be uncapped, unlimited and always-on.
 */
export const couponFormSchema = z
  .object({
    code: z
      .string()
      .trim()
      .min(2, "At least 2 characters")
      .max(40)
      .regex(/^[A-Za-z0-9_-]+$/, "Letters, digits, - and _ only"),
    description: z.string().trim().max(200),
    kind: z.enum(COUPON_KINDS),
    value: z.string().trim().min(1, "Enter an amount or percentage"),
    max_discount: z.string().trim(),
    min_subtotal: z.string().trim(),
    scope: z.enum(COUPON_SCOPES),
    category_id: z.string(),
    product_id: z.string(),
    starts_at: z.string().trim(),
    ends_at: z.string().trim(),
    max_redemptions: z.string().trim(),
    max_per_customer: z.string().trim(),
    is_active: z.boolean(),
  })
  .superRefine((values, ctx) => {
    const amount = (raw: string) => raw === "" || /^\d+(\.\d{1,2})?$/.test(raw);
    const whole = (raw: string) => raw === "" || /^\d+$/.test(raw);

    if (!amount(values.value)) {
      ctx.addIssue({ path: ["value"], code: "custom", message: "Enter a valid amount" });
    } else if (values.kind === "percent" && Number(values.value) > 100) {
      ctx.addIssue({ path: ["value"], code: "custom", message: "A percentage cannot exceed 100" });
    }
    if (!amount(values.max_discount)) {
      ctx.addIssue({ path: ["max_discount"], code: "custom", message: "Enter a valid amount" });
    }
    if (!amount(values.min_subtotal)) {
      ctx.addIssue({ path: ["min_subtotal"], code: "custom", message: "Enter a valid amount" });
    }
    if (!whole(values.max_redemptions)) {
      ctx.addIssue({ path: ["max_redemptions"], code: "custom", message: "Whole numbers only" });
    }
    if (!whole(values.max_per_customer)) {
      ctx.addIssue({ path: ["max_per_customer"], code: "custom", message: "Whole numbers only" });
    }
    if (values.scope === "category" && !values.category_id) {
      ctx.addIssue({ path: ["category_id"], code: "custom", message: "Pick a category" });
    }
    if (values.scope === "product" && !values.product_id) {
      ctx.addIssue({ path: ["product_id"], code: "custom", message: "Pick a product" });
    }
    for (const field of ["starts_at", "ends_at"] as const) {
      const raw = values[field];
      if (raw && Number.isNaN(Date.parse(raw))) {
        ctx.addIssue({ path: [field], code: "custom", message: "Use a date like 2026-12-31" });
      }
    }
  })
  .transform((values) => ({
    code: values.code.toUpperCase(),
    description: values.description || null,
    kind: values.kind,
    value: values.value,
    max_discount: values.max_discount || null,
    min_subtotal: values.min_subtotal || "0",
    scope: values.scope,
    category_id: values.scope === "category" ? values.category_id : null,
    product_id: values.scope === "product" ? values.product_id : null,
    starts_at: values.starts_at ? new Date(values.starts_at).toISOString() : null,
    ends_at: values.ends_at ? new Date(values.ends_at).toISOString() : null,
    max_redemptions: values.max_redemptions ? Number(values.max_redemptions) : null,
    max_per_customer: values.max_per_customer ? Number(values.max_per_customer) : null,
    is_active: values.is_active,
  }));

export type CouponFormInput = z.input<typeof couponFormSchema>;
export type CouponPayload = z.output<typeof couponFormSchema>;
