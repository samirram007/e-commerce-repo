import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCoupon,
  deactivateCoupon,
  fetchCoupons,
  fetchRedemptions,
  updateCoupon,
} from "./api";
import type { ListState } from "../../hooks/use-list-state";
import { listQueryKey } from "../../hooks/use-list-state";
import type { CouponPayload } from "./schemas";

export const promotionsKeys = {
  all: ["promotions"] as const,
  coupons: (list: ListState) => [...promotionsKeys.all, "coupons", ...listQueryKey(list)] as const,
  redemptions: (couponId: string) => [...promotionsKeys.all, "redemptions", couponId] as const,
};

/**
 * List query options. The key includes every server-side param (page, sort,
 * search), so each view is cached separately and invalidated together under
 * `promotionsKeys.all` after a mutation.
 */
export function couponsQueryOptions(list: ListState) {
  return queryOptions({
    queryKey: promotionsKeys.coupons(list),
    queryFn: () =>
      fetchCoupons({
        page: list.page,
        page_size: list.pageSize,
        ...(list.search.trim() ? { search: list.search.trim() } : {}),
        ...(list.sort ? { sort: list.sort, order: list.order } : {}),
      }),
  });
}

export function redemptionsQueryOptions(couponId: string) {
  return queryOptions({
    queryKey: promotionsKeys.redemptions(couponId),
    queryFn: () => fetchRedemptions(couponId),
    enabled: Boolean(couponId),
  });
}

export function useCreateCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CouponPayload) => createCoupon(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: promotionsKeys.all }),
  });
}

export function useUpdateCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: CouponPayload }) => updateCoupon(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: promotionsKeys.all }),
  });
}

export function useDeactivateCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deactivateCoupon(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: promotionsKeys.all }),
  });
}
