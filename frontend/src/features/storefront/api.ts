/**
 * Storefront API client — the public shopping surface.
 *
 * The shop is usable without an account, so requests carry the store's
 * `X-Company-Id` plus the browser's `X-Cart-Token` and `X-Anon-Id`. When the
 * shopper is signed in to the ERP the bearer token is attached as well, which
 * lets the backend attach favorites/watchlist to their account.
 */
import axios, { type AxiosError, type AxiosInstance } from "axios";
import { getAccessToken } from "../../auth/session";
import { ApiError, NETWORK_ERROR } from "../../lib/error-handling";
import { anonId, cartToken, cachedCompanyId, STOREFRONT_SLUG } from "./store";
import type {
  CheckoutPayload,
  PaymentMethod,
  PincodeCheck,
  ShopAddress,
  ShopCart,
  ShopCategory,
  ShopInterests,
  ShopOrder,
  ShopProduct,
  ShopProductDetail,
  ShopProductPage,
  ShopReturn,
  StoreInfo,
  RazorpayOrderIntent,
  RazorpayVerifyPayload,
} from "./types";

/** Axios instance bound to the public storefront API. */
export const shopApi: AxiosInstance = axios.create({
  baseURL: "/api/v1/storefront/shop",
  timeout: 15000,
  withCredentials: true,
});

shopApi.interceptors.request.use((config) => {
  const companyId = cachedCompanyId();
  if (companyId) config.headers["X-Company-Id"] = companyId;
  config.headers["X-Cart-Token"] = cartToken();
  config.headers["X-Anon-Id"] = anonId();
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

shopApi.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorEnvelope>) => {
    const body = error.response?.data?.error;
    return Promise.reject(
      new ApiError({
        code: body?.code ?? NETWORK_ERROR,
        message: body?.message ?? error.message,
        status: error.response?.status ?? 0,
        details: body?.details,
      }),
    );
  },
);

/** Resolve the public store (company, currency, guest-checkout flag) by slug. */
export async function fetchStore(slug: string = STOREFRONT_SLUG): Promise<StoreInfo> {
  const response = await shopApi.get<StoreInfo>(`/store/${slug}`);
  return response.data;
}

export interface ProductFilters {
  q?: string;
  category?: string;
  minPrice?: string;
  maxPrice?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

export async function fetchProducts(filters: ProductFilters = {}): Promise<ShopProductPage> {
  const params: Record<string, string | number> = {};
  if (filters.q) params.q = filters.q;
  if (filters.category) params.category = filters.category;
  if (filters.minPrice) params.min_price = filters.minPrice;
  if (filters.maxPrice) params.max_price = filters.maxPrice;
  if (filters.sort) params.sort = filters.sort;
  params.limit = filters.limit ?? 24;
  params.offset = filters.offset ?? 0;
  const response = await shopApi.get<ShopProductPage>("/products", { params });
  return response.data;
}

export async function fetchCategories(): Promise<ShopCategory[]> {
  const response = await shopApi.get<ShopCategory[]>("/categories");
  return response.data;
}

export async function fetchTrending(limit = 8): Promise<ShopProduct[]> {
  const response = await shopApi.get<ShopProduct[]>("/trending", { params: { limit } });
  return response.data;
}

export async function fetchProduct(productId: string, countView = false): Promise<ShopProductDetail> {
  const response = await shopApi.get<ShopProductDetail>(`/products/${productId}`, {
    params: { count_view: countView },
  });
  return response.data;
}

export async function fetchInterests(): Promise<ShopInterests> {
  const response = await shopApi.get<ShopInterests>("/interests");
  return response.data;
}

export async function toggleInterest(
  kind: "favorite" | "watchlist",
  productId: string,
): Promise<{ kind: string; product_id: string; active: boolean }> {
  const response = await shopApi.post("/interests/toggle", { kind, product_id: productId });
  return response.data;
}

export async function fetchPincode(pincode: string): Promise<PincodeCheck> {
  const response = await shopApi.get<PincodeCheck>(`/pincode/${encodeURIComponent(pincode)}`);
  return response.data;
}

export async function fetchCart(): Promise<ShopCart> {
  const response = await shopApi.get<ShopCart>("/cart");
  return response.data;
}

export async function addCartItem(productId: string, qty: string): Promise<ShopCart> {
  const response = await shopApi.post<ShopCart>("/cart/items", { product_id: productId, qty });
  return response.data;
}

export async function updateCartItem(itemId: string, qty: string): Promise<ShopCart> {
  const response = await shopApi.patch<ShopCart>(`/cart/items/${itemId}`, { qty });
  return response.data;
}

export async function removeCartItem(itemId: string): Promise<ShopCart> {
  const response = await shopApi.delete<ShopCart>(`/cart/items/${itemId}`);
  return response.data;
}

export async function clearCart(): Promise<ShopCart> {
  const response = await shopApi.delete<ShopCart>("/cart");
  return response.data;
}

export async function fetchPaymentMethods(pincode?: string): Promise<PaymentMethod[]> {
  const response = await shopApi.get<PaymentMethod[]>("/payment-methods", {
    params: pincode ? { pincode } : {},
  });
  return response.data;
}

export async function fetchAddresses(): Promise<ShopAddress[]> {
  const response = await shopApi.get<ShopAddress[]>("/addresses");
  return response.data;
}

export async function createAddress(payload: Omit<ShopAddress, "id">): Promise<ShopAddress> {
  const response = await shopApi.post<ShopAddress>("/addresses", payload);
  return response.data;
}

export async function updateAddress(
  id: string,
  payload: Omit<ShopAddress, "id">,
): Promise<ShopAddress> {
  const response = await shopApi.put<ShopAddress>(`/addresses/${id}`, payload);
  return response.data;
}

export async function deleteAddress(id: string): Promise<void> {
  await shopApi.delete(`/addresses/${id}`);
}

/** Place the order for the current cart token (idempotent per key). */
export async function placeOrder(payload: CheckoutPayload, idempotencyKey: string): Promise<ShopOrder> {
  const response = await shopApi.post<ShopOrder>("/checkout", payload, {
    headers: { "Idempotency-Key": idempotencyKey },
  });
  return response.data;
}

export async function fetchOrders(): Promise<ShopOrder[]> {
  const response = await shopApi.get<ShopOrder[]>("/orders");
  return response.data;
}

/** Pay a previously placed (unpaid) order — "continue purchase" (sandbox). */
export async function payOrder(orderId: string, method: string): Promise<ShopOrder> {
  const response = await shopApi.post<ShopOrder>(`/orders/${orderId}/pay`, { method });
  return response.data;
}

/** Create (or reuse) the Razorpay order that Checkout opens with. */
export async function createRazorpayOrder(orderId: string): Promise<RazorpayOrderIntent> {
  const response = await shopApi.post<RazorpayOrderIntent>(`/orders/${orderId}/razorpay`);
  return response.data;
}

/** Server verifies the Checkout signature, then marks the order paid. */
export async function verifyRazorpayPayment(
  orderId: string,
  payload: RazorpayVerifyPayload,
): Promise<ShopOrder> {
  const response = await shopApi.post<ShopOrder>(`/orders/${orderId}/razorpay/verify`, payload);
  return response.data;
}

/** Cancel an order; paid orders are refunded and credited server-side. */
export async function cancelOrder(orderId: string): Promise<ShopOrder> {
  const response = await shopApi.post<ShopOrder>(`/orders/${orderId}/cancel`);
  return response.data;
}

export async function fetchOrderReturns(orderId: string): Promise<ShopReturn[]> {
  const response = await shopApi.get<ShopReturn[]>(`/orders/${orderId}/returns`);
  return response.data;
}

export async function requestOrderReturn(
  orderId: string,
  lines: { product_id: string; qty: number }[],
  notes?: string,
): Promise<ShopReturn> {
  const response = await shopApi.post<ShopReturn>(`/orders/${orderId}/returns`, { lines, notes });
  return response.data;
}
