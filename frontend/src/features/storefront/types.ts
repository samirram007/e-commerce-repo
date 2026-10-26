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
  image_url: string | null;
}

export interface ShopProductDetail extends ShopProduct {
  category_name: string | null;
  related: ShopProduct[];
  image_url: string | null;
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
  /** Always true on a 200: malformed PIN codes are rejected with 400. */
  valid: boolean;
  /** Indian state/UT derived from the PIN code's postal circle. */
  state: string | null;
  city: string | null;
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
  /** Resolved unit price (server-side price list). */
  price: string;
  unit_price: string;
  tax_amount: string;
  /** Qty × unit price + tax, authoritative from the cart quote. */
  line_total: string;
  stock_type: string;
  image_url: string | null;
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

/** Tax charged at one GST rate (the UI shows the CGST/SGST halves in the label). */
export interface ShopTaxBreakup {
  rate: string;
  amount: string;
}

export interface ShopQuote {
  cart_id: string;
  lines: ShopQuoteLine[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  /** One entry per GST rate; empty when nothing is taxable. */
  tax_breakup: ShopTaxBreakup[];
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
  available: boolean;
  /** Why an option is unavailable (e.g. "not_configured" for Razorpay without keys). */
  reason?: string | null;
}

/** Gateway order returned by `POST /orders/{id}/razorpay`. */
export interface RazorpayOrderIntent {
  key_id: string;
  /** True when the backend runs the simulated gateway (no credentials). */
  demo?: boolean;
  razorpay_order_id: string;
  /** Amount in paise. */
  amount: number;
  currency: string;
  order_id: string;
  doc_number: string;
  store_name: string;
  description: string;
}

export interface RazorpayVerifyPayload {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface ShopReturnLine {
  id: string;
  product_id: string;
  qty: string;
  unit_price: string;
  disposition: string;
}

export interface ShopReturn {
  id: string;
  doc_number: string;
  order_id: string;
  status: string;
  requested_at: string | null;
  completed_at: string | null;
  credit_note_id: string | null;
  refund_payment_id: string | null;
  notes: string | null;
  lines: ShopReturnLine[];
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
  cancelled_at?: string | null;
  /** cancelled_by_customer | cancelled_by_staff | payment_timeout */
  cancel_reason?: string | null;
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
  /** Method of the latest receipt row (cash = cash on delivery). */
  payment_method?: string | null;
  /** Status of that receipt row: pending | succeeded | voided | … */
  payment_status?: string | null;
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
