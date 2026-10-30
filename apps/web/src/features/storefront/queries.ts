/** TanStack Query options for the public storefront. */
import { queryOptions } from "@tanstack/react-query";
import {
  fetchAddresses,
  fetchCart,
  fetchCategories,
  fetchInterests,
  fetchOrderReturns,
  fetchOrders,
  fetchPaymentMethods,
  fetchPincode,
  fetchOrderFeedbackState,
  fetchProduct,
  fetchProductReviews,
  fetchProducts,
  fetchShippingOptions,
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
  orderReturns: (orderId: string) => ["shop", "order-returns", orderId] as const,
  pincode: (pincode: string) => ["shop", "pincode", pincode] as const,
  paymentMethods: (pincode?: string) => ["shop", "payment-methods", pincode ?? ""] as const,
  shippingOptions: (pincode?: string) => ["shop", "shipping-options", pincode ?? ""] as const,
  productReviews: (productId: string) => ["shop", "product-reviews", productId] as const,
  orderFeedback: (orderId: string) => ["shop", "order-feedback", orderId] as const,
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

export function orderReturnsQueryOptions(orderId: string) {
  return queryOptions({
    queryKey: shopKeys.orderReturns(orderId),
    queryFn: () => fetchOrderReturns(orderId),
  });
}

/** Indian PIN codes are exactly six digits (and never start with 0). */
export function isValidPincode(pincode: string): boolean {
  return /^[1-9]\d{5}$/.test(pincode.trim());
}

export function pincodeQueryOptions(pincode: string) {
  const normalized = pincode.trim();
  return queryOptions({
    queryKey: shopKeys.pincode(normalized),
    queryFn: () => fetchPincode(normalized),
    enabled: isValidPincode(normalized),
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

export function shippingOptionsQueryOptions(pincode?: string) {
  return queryOptions({
    queryKey: shopKeys.shippingOptions(pincode),
    queryFn: () => fetchShippingOptions(pincode),
    staleTime: 60_000,
  });
}

/** Approved reviews shown on a product page. */
export function productReviewsQueryOptions(productId: string) {
  return queryOptions({
    queryKey: shopKeys.productReviews(productId),
    queryFn: () => fetchProductReviews(productId),
    staleTime: 60_000,
  });
}

/** Reviewable items + existing feedback for one of the shopper's orders. */
export function orderFeedbackQueryOptions(orderId: string) {
  return queryOptions({
    queryKey: shopKeys.orderFeedback(orderId),
    queryFn: () => fetchOrderFeedbackState(orderId),
    enabled: Boolean(orderId),
  });
}
