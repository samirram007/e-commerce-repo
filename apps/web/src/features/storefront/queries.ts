/** TanStack Query options for the public storefront. */
import { queryOptions } from "@tanstack/react-query";
import {
  fetchAddresses,
  fetchCart,
  fetchCategories,
  fetchInterests,
  fetchOrders,
  fetchPaymentMethods,
  fetchPincode,
  fetchProduct,
  fetchProducts,
  fetchTrending,
  type ProductFilters,
} from "./api";

export const shopKeys = {
  all: ["shop"] as const,
  categories: ["shop", "categories"] as const,
  products: (filters: ProductFilters) => ["shop", "products", filters] as const,
  trending: ["shop", "trending"] as const,
  product: (id: string) => ["shop", "product", id] as const,
  interests: ["shop", "interests"] as const,
  cart: ["shop", "cart"] as const,
  addresses: ["shop", "addresses"] as const,
  orders: ["shop", "orders"] as const,
  pincode: (pincode: string) => ["shop", "pincode", pincode] as const,
  paymentMethods: (pincode?: string) => ["shop", "payment-methods", pincode ?? ""] as const,
};

export function categoriesQueryOptions() {
  return queryOptions({ queryKey: shopKeys.categories, queryFn: fetchCategories });
}

export function productsQueryOptions(filters: ProductFilters) {
  return queryOptions({ queryKey: shopKeys.products(filters), queryFn: () => fetchProducts(filters) });
}

export function trendingQueryOptions(limit = 8) {
  return queryOptions({ queryKey: shopKeys.trending, queryFn: () => fetchTrending(limit) });
}

export function productQueryOptions(productId: string, countView = false) {
  return queryOptions({
    queryKey: shopKeys.product(productId),
    queryFn: () => fetchProduct(productId, countView),
  });
}

export function interestsQueryOptions() {
  return queryOptions({ queryKey: shopKeys.interests, queryFn: fetchInterests });
}

export function cartQueryOptions() {
  return queryOptions({ queryKey: shopKeys.cart, queryFn: fetchCart });
}

export function addressesQueryOptions() {
  return queryOptions({ queryKey: shopKeys.addresses, queryFn: fetchAddresses });
}

export function ordersQueryOptions() {
  return queryOptions({ queryKey: shopKeys.orders, queryFn: fetchOrders });
}

export function pincodeQueryOptions(pincode: string) {
  return queryOptions({
    queryKey: shopKeys.pincode(pincode),
    queryFn: () => fetchPincode(pincode),
    enabled: pincode.trim().length >= 4,
    staleTime: 5 * 60_000,
  });
}

export function paymentMethodsQueryOptions(pincode?: string) {
  return queryOptions({
    queryKey: shopKeys.paymentMethods(pincode),
    queryFn: () => fetchPaymentMethods(pincode),
    staleTime: 60_000,
  });
}
