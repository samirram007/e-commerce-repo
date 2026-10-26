import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addCartItem,
  cancelOrder,
  checkout,
  fetchCart,
  fetchOrder,
  fetchOrders,
  payOrder,
  quoteCart,
  removeCartItem,
  updateCartItem,
} from "./api";
import type { CheckoutPayload, PayPayload } from "./schemas";

export interface OrderFilters {
  status?: string;
  customerId?: string;
}

export const orderKeys = {
  all: ["orders"] as const,
  list: (filters: OrderFilters) => [...orderKeys.all, "list", filters] as const,
  detail: (id: string) => [...orderKeys.all, "detail", id] as const,
  cart: () => [...orderKeys.all, "cart"] as const,
  quote: (shippingTotal: string) => [...orderKeys.all, "quote", shippingTotal] as const,
};

export function ordersQueryOptions(filters: OrderFilters = {}) {
  return queryOptions({
    queryKey: orderKeys.list(filters),
    queryFn: () => fetchOrders(filters),
  });
}

export function orderQueryOptions(id: string, enabled = true) {
  return queryOptions({
    queryKey: orderKeys.detail(id),
    queryFn: () => fetchOrder(id),
    enabled: enabled && Boolean(id),
  });
}

export function cartQueryOptions(enabled = true) {
  return queryOptions({
    queryKey: orderKeys.cart(),
    queryFn: fetchCart,
    enabled,
  });
}

export function quoteQueryOptions(shippingTotal: string, enabled = true) {
  return queryOptions({
    queryKey: orderKeys.quote(shippingTotal),
    queryFn: () => quoteCart(shippingTotal),
    enabled,
  });
}

export function usePayOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: PayPayload }) => payOrder(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelOrder(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}

export function useAddCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { product_id: string; qty: string }) => addCartItem(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, qty }: { itemId: string; qty: string }) => updateCartItem(itemId, qty),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => removeCartItem(itemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}

export function useCheckout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CheckoutPayload) => checkout(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  });
}
