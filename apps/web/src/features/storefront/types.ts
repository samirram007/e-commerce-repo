/** Payload types returned by the public storefront API (`/api/v1/storefront/shop`). */

export interface StoreInfo {
  company_id: string;
  slug: string;
  name: string;
  currency: string;
  allow_guest_checkout: boolean;
}

export interface ShopCategory {
  id: string;
  name: string;
  parent_id: string | null;
  product_count: number;
}

export interface ShopProduct {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  category_id: string | null;
  price: string;
  stock_type: string;
  view_count: number;
}

export interface ShopProductDetail extends ShopProduct {
  category_name: string | null;
  related: ShopProduct[];
}

export interface ShopProductPage {
  items: ShopProduct[];
  total: number;
}

export interface ShopInterests {
  favorite: ShopProduct[];
  watchlist: ShopProduct[];
}

export interface PincodeCheck {
  pincode: string;
  deliverable: boolean;
  eta_days: number | null;
  cod_allowed: boolean;
  configured: boolean;
}

export interface ShopCartItem {
  id: string;
  product_id: string;
  qty: string;
  name: string;
  sku: string;
  price: string;
}

export interface ShopQuoteLine {
  item_id: string;
  product_id: string;
  sku: string;
  qty: string;
  unit_price: string;
  tax_amount: string;
  line_total: string;
}

export interface ShopQuote {
  cart_id: string;
  lines: ShopQuoteLine[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  shipping_total: string;
  total: string;
  currency: string;
}

export interface ShopCart {
  id: string;
  status: string;
  token: string;
  items: ShopCartItem[];
  quote: ShopQuote;
}

export interface PaymentMethod {
  code: string;
  label: string;
  provider: string;
  /** Active credential mode of the resolved gateway ("test" | "live"); null for offline methods. */
  mode?: string | null;
  available: boolean;
}

/** What the browser needs to complete a payment with the active gateway. */
export interface ShopPayment {
  provider: string;
  mode: string | null;
  payment_id?: string;
  client_payload?: Record<string, unknown>;
  status?: string;
}

export interface ShopAddress {
  id: string;
  label: string;
  name: string;
  phone: string | null;
  line1: string;
  line2: string | null;
  city: string | null;
  region: string | null;
  pincode: string | null;
  country: string;
  is_default: boolean;
  notes: string | null;
}

export interface ShopOrderItem {
  product_id: string;
  name: string;
  sku: string;
  qty: string;
  unit_price: string;
  line_total: string;
}

export interface ShopOrder {
  id: string;
  doc_number: string;
  status: string;
  payment_state: string;
  order_date: string;
  currency: string;
  subtotal: string;
  tax_total: string;
  shipping_total: string;
  total: string;
  invoice_id: string | null;
  shipping_address: string | null;
  items: ShopOrderItem[];
  payment_method?: string;
  payment?: ShopPayment | null;
  email?: string;
  replayed?: boolean;
}

export interface CheckoutPayload {
  name: string;
  email: string;
  phone?: string;
  address: {
    line1: string;
    line2?: string;
    city?: string;
    region?: string;
    pincode?: string;
    country?: string;
  };
  payment_method: string;
  shipping_total?: string;
  notes?: string;
}
