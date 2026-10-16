import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  type Cart,
  cartQuoteSchema,
  type CartQuote,
  cartSchema,
  type CheckoutPayload,
  checkoutResultSchema,
  type CheckoutResult,
  type Order,
  orderDetailSchema,
  type OrderDetail,
  orderSchema,
  type PayPayload,
  payResultSchema,
  type PayResult,
} from "./schemas";

function idempotencyKey(): string {
  return crypto.randomUUID();
}

export async function fetchOrders(
  filters: { status?: string; customerId?: string } = {},
): Promise<Order[]> {
  const { data } = await api.get("/storefront/orders", {
    params: {
      status: filters.status || undefined,
      customer_id: filters.customerId || undefined,
    },
  });
  return z.array(orderSchema).parse(data);
}

export async function fetchOrder(id: string): Promise<OrderDetail> {
  const { data } = await api.get(`/storefront/orders/${id}`);
  return orderDetailSchema.parse(data);
}

export async function payOrder(id: string, input: PayPayload): Promise<PayResult> {
  const { data } = await api.post(`/storefront/orders/${id}/pay`, input, {
    headers: { "Idempotency-Key": idempotencyKey() },
  });
  return payResultSchema.parse(data);
}

export async function cancelOrder(id: string): Promise<{ id: string; status: string }> {
  const { data } = await api.post(`/storefront/orders/${id}/cancel`);
  return z.object({ id: z.string(), status: z.string() }).parse(data);
}

export async function fetchCart(): Promise<Cart> {
  const { data } = await api.get("/storefront/cart");
  return cartSchema.parse(data);
}

export async function addCartItem(input: { product_id: string; qty: string }): Promise<Cart> {
  const { data } = await api.post("/storefront/cart/items", input);
  return cartSchema.parse(data);
}

export async function updateCartItem(itemId: string, qty: string): Promise<Cart> {
  const { data } = await api.patch(`/storefront/cart/items/${itemId}`, { qty });
  return cartSchema.parse(data);
}

export async function removeCartItem(itemId: string): Promise<Cart> {
  const { data } = await api.delete(`/storefront/cart/items/${itemId}`);
  return cartSchema.parse(data);
}

export async function quoteCart(shippingTotal: string): Promise<CartQuote> {
  const { data } = await api.get("/storefront/cart/quote", {
    params: { shipping_total: shippingTotal },
  });
  return cartQuoteSchema.parse(data);
}

export async function checkout(input: CheckoutPayload): Promise<CheckoutResult> {
  const { data } = await api.post("/storefront/checkout", input, {
    headers: { "Idempotency-Key": idempotencyKey() },
  });
  return checkoutResultSchema.parse(data);
}
