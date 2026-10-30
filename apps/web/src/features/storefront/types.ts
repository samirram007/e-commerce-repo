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
  /** Coupon share taken off this line ("0.00" when none applies). */
  discount?: string;
  tax_amount: string;
  line_total: string;
}

/** Promo code state of a cart quote: priced whether or not it is still usable. */
export interface ShopCoupon {
  code: string;
  description: string | null;
  discount_total: string;
  valid: boolean;
  /** Machine code + message explaining why a stored code is not applied. */
  reason: string | null;
  message: string | null;
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
  /** Null when no promo code is on the cart. */
  coupon?: ShopCoupon | null;
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

/**
 * A delivery option at checkout: the carriers the shop enabled (or its standard
 * rule price when none is configured), priced and described as the admin set it.
 */
export interface ShopShippingOption {
  code: string;
  label: string;
  price: string;
  /** `carrier` (live quote), `rules`, or `rules_fallback` when a carrier could not quote. */
  rate_source: string;
  /** Carrier code to send back at checkout; null for the shop's standard option. */
  carrier: string | null;
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
  cancelled_at?: string | null;
  /** cancelled_by_customer | cancelled_by_staff | payment_timeout */
  cancel_reason?: string | null;
  status: string;
  payment_state: string;
  order_date: string;
  currency: string;
  subtotal: string;
  /** Coupon discount taken off the order ("0.0000" when none). */
  discount_total?: string;
  coupon_code?: string | null;
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
  /** Provider intent returned by checkout / pay (online methods only). */
  payment?: ShopPayment | null;
  email?: string;
  replayed?: boolean;
  /** When the delivery landed — the return window starts here. */
  delivered_at?: string | null;
  /** Last day a return may be requested (null when the shop sets no window). */
  return_by?: string | null;
  /** True once the order is paid, i.e. its items can be reviewed. */
  can_review?: boolean;
}

/** A published product review (approved reviews only reach the storefront). */
export interface ShopReview {
  id: string;
  product_id: string;
  order_id: string;
  rating: number;
  title: string | null;
  body: string | null;
  status: string;
  created_at: string | null;
}

export interface ShopReviewSummary {
  average: string | null;
  count: number;
}

export interface ShopProductReviews {
  summary: ShopReviewSummary;
  items: ShopReview[];
}

/** One purchasable line of an order, with what the shopper already reviewed. */
export interface ShopReviewableItem {
  product_id: string;
  order_line_id: string | null;
  sku: string;
  name: string;
  qty: string;
  image_file_id: string | null;
  reviewed: boolean;
  review_status: string | null;
  rating: number | null;
  review_id: string | null;
}

/** Private order-experience feedback (delivery / packaging / service). */
export interface ShopOrderFeedback {
  id: string;
  order_id: string;
  delivery_rating: number | null;
  packaging_rating: number | null;
  service_rating: number | null;
  comment: string | null;
  created_at: string | null;
}

export interface ShopOrderFeedbackState {
  order_id: string;
  can_review: boolean;
  items: ShopReviewableItem[];
  reviews: ShopReview[];
  order_feedback: ShopOrderFeedback | null;
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
  /** Carrier the shopper picked (see `fetchShippingOptions`); omitted for standard delivery. */
  shipping_carrier?: string;
  shipping_total?: string;
  notes?: string;
}
