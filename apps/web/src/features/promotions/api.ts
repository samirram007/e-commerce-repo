import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  couponPageSchema,
  couponSchema,
  redemptionSchema,
  type Coupon,
  type CouponPage,
  type CouponPayload,
  type CouponRedemption,
} from "./schemas";

/**
 * Server-side list: `params` comes from `useListState().params`
 * ({page, page_size, search, sort, order}).
 */
export async function fetchCoupons(params: Record<string, string | number>): Promise<CouponPage> {
  const { data } = await api.get("/promotions", { params });
  return couponPageSchema.parse(data);
}

export async function createCoupon(input: CouponPayload): Promise<Coupon> {
  const { data } = await api.post("/promotions", input);
  return couponSchema.parse(data);
}

export async function updateCoupon(id: string, input: CouponPayload): Promise<Coupon> {
  const { data } = await api.patch(`/promotions/${id}`, input);
  return couponSchema.parse(data);
}

/** Stops a code from being usable; the redemption history is kept. */
export async function deactivateCoupon(id: string): Promise<Coupon> {
  const { data } = await api.delete(`/promotions/${id}`);
  return couponSchema.parse(data);
}

export async function fetchRedemptions(couponId: string): Promise<CouponRedemption[]> {
  const { data } = await api.get(`/promotions/${couponId}/redemptions`);
  return z.array(redemptionSchema).parse(data);
}
