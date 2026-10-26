import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  StatusBadge,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate, formatMoney, formatQty, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { productsQueryOptions } from "../catalog/queries";
import { customersQueryOptions } from "../partners/queries";
import {
  cartItemFormSchema,
  type CartItemFormInput,
  checkoutFormSchema,
  type CheckoutFormInput,
  ORDER_STATUSES,
  type Order,
  type OrderLine,
  type PayFormInput,
  payFormSchema,
} from "./schemas";
import {
  cartQueryOptions,
  orderQueryOptions,
  ordersQueryOptions,
  quoteQueryOptions,
  useAddCartItem,
  useCancelOrder,
  useCheckout,
  usePayOrder,
  useRemoveCartItem,
  useUpdateCartItem,
} from "./queries";

const EMPTY_CART_ITEM: CartItemFormInput = { product_id: "", qty: "1" };
const EMPTY_CHECKOUT: CheckoutFormInput = {
  customer_id: "",
  shipping_address: "",
  billing_address: "",
  shipping_total: "0",
  notes: "",
};
const EMPTY_PAY: PayFormInput = { method: "mock_gateway", provider: "mock" };

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  ...ORDER_STATUSES.map((status) => ({ value: status, label: titleCase(status) })),
];

const PAY_METHOD_OPTIONS = [
  { value: "mock_gateway", label: "Mock gateway" },
  { value: "card", label: "Card" },
  { value: "bank_transfer", label: "Bank transfer" },
];

function isAmount(value: string): boolean {
  return /^\d+(\.\d+)?$/.test(value.trim());
}

export function OrdersPage() {
  const { has } = usePermissions();
  const canOrder = has("storefront.cart.use");

  const [status, setStatus] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const [cartOpen, setCartOpen] = useState(false);
  const [cartItemForm, setCartItemForm] = useState<CartItemFormInput>(EMPTY_CART_ITEM);
  const [cartItemErrors, setCartItemErrors] = useState<Record<string, string>>({});
  const [qtyDrafts, setQtyDrafts] = useState<Record<string, string>>({});
  const [checkoutForm, setCheckoutForm] = useState<CheckoutFormInput>(EMPTY_CHECKOUT);
  const [checkoutErrors, setCheckoutErrors] = useState<Record<string, string>>({});

  const [payForm, setPayForm] = useState<PayFormInput>(EMPTY_PAY);
  const [payErrors, setPayErrors] = useState<Record<string, string>>({});

  const orders = useQuery(
    ordersQueryOptions({ status: status ?? undefined, customerId: customerId ?? undefined }),
  );
  const detail = useQuery(orderQueryOptions(selectedOrderId ?? "", selectedOrderId !== null));
  const cart = useQuery(cartQueryOptions(cartOpen));
  const shippingTotal = checkoutForm.shipping_total ?? "0";
  const quote = useQuery(quoteQueryOptions(shippingTotal, cartOpen && isAmount(shippingTotal)));
  const products = useQuery(productsQueryOptions());
  const customers = useQuery(customersQueryOptions());

  const addCartItem = useAddCartItem();
  const updateCartItem = useUpdateCartItem();
  const removeCartItem = useRemoveCartItem();
  const checkout = useCheckout();
  const payOrder = usePayOrder();
  const cancelOrder = useCancelOrder();

  const productOptions = useMemo(
    () =>
      (products.data?.items ?? [])
        .filter((product) => product.is_sellable && product.is_active)
        .map((product) => ({
          value: product.id,
          label: `${product.sku} — ${product.name}`,
          hint: formatMoney(product.base_price),
        })),
    [products.data],
  );

  const productLabels = useMemo(() => {
    const map = new Map<string, string>();
    for (const product of products.data?.items ?? []) {
      map.set(product.id, `${product.sku} — ${product.name}`);
    }
    return map;
  }, [products.data]);

  const customerOptions = useMemo(
    () => (customers.data ?? []).map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })),
    [customers.data],
  );

  // Filter variant includes a reset entry; checkout's customerOptions does not.
  const customerFilterOptions = useMemo(
    () => [{ value: "", label: "All customers" }, ...customerOptions],
    [customerOptions],
  );

  const activeQuote = quote.data ?? cart.data?.quote;

  function openCart() {
    setCartItemForm(EMPTY_CART_ITEM);
    setCartItemErrors({});
    setCheckoutForm(EMPTY_CHECKOUT);
    setCheckoutErrors({});
    setQtyDrafts({});
    setCartOpen(true);
  }

  function addToCart() {
    const parsed = cartItemFormSchema.safeParse(cartItemForm);
    if (!parsed.success) {
      setCartItemErrors(fieldErrors(parsed.error));
      return;
    }
    setCartItemErrors({});
    addCartItem.mutate(
      { product_id: parsed.data.product_id, qty: parsed.data.qty },
      { onSuccess: () => setCartItemForm(EMPTY_CART_ITEM) },
    );
  }

  function submitCheckout() {
    const parsed = checkoutFormSchema.safeParse(checkoutForm);
    if (!parsed.success) {
      setCheckoutErrors(fieldErrors(parsed.error));
      return;
    }
    setCheckoutErrors({});
    checkout.mutate(parsed.data, {
      onSuccess: () => {
        setCartOpen(false);
        setCheckoutForm(EMPTY_CHECKOUT);
      },
    });
  }

  function submitPay() {
    if (!selectedOrderId) return;
    const parsed = payFormSchema.safeParse(payForm);
    if (!parsed.success) {
      setPayErrors(fieldErrors(parsed.error));
      return;
    }
    setPayErrors({});
    payOrder.mutate({ id: selectedOrderId, input: parsed.data });
  }

  const columns: Column<Order>[] = [
    { key: "doc", header: "Order", render: (o) => <strong>{o.doc_number}</strong> },
    { key: "date", header: "Date", render: (o) => formatDate(o.order_date) },
    { key: "status", header: "Status", render: (o) => <StatusBadge status={o.status} /> },
    { key: "payment", header: "Payment", render: (o) => <StatusBadge status={o.payment_state} /> },
    { key: "total", header: "Total", align: "right", render: (o) => formatMoney(o.total, o.currency) },
    {
      key: "actions",
      header: "",
      render: (o) => (
        <Button variant="secondary" onClick={() => setSelectedOrderId(o.id)}>
          View
        </Button>
      ),
    },
  ];

  const lineColumns: Column<OrderLine>[] = [
    { key: "sku", header: "SKU", render: (l) => l.sku },
    { key: "qty", header: "Qty", align: "right", render: (l) => formatQty(l.qty) },
    { key: "price", header: "Unit price", align: "right", render: (l) => formatMoney(l.unit_price) },
    { key: "tax", header: "Tax", align: "right", render: (l) => formatMoney(l.tax_amount) },
    { key: "total", header: "Line total", align: "right", render: (l) => formatMoney(l.line_total) },
  ];

  const detailOrder = detail.data;

  return (
    <>
      <PageHeader
        title="Sales Orders"
        description="Storefront orders, payments and cart checkout"
        actions={canOrder ? <Button onClick={openCart}>New order</Button> : null}
      />

      <Card>
        <div className="form-row">
          <Field label="Status">
            <SheetSelect
              value={status ?? ""}
              options={STATUS_OPTIONS}
              onChange={(value) => setStatus(value || null)}
              placeholder="All statuses"
            />
          </Field>
          <Field label="Customer">
            <SheetSelect
              value={customerId ?? ""}
              options={customerFilterOptions}
              onChange={(value) => setCustomerId(value || null)}
              placeholder="All customers"
              loading={customers.isLoading}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={orders.data}
          rowKey={(o) => o.id}
          loading={orders.isLoading}
          error={orders.error}
          onRetry={() => orders.refetch()}
          empty={<EmptyState title="No orders" message="Create an order from the cart." />}
        />
      </Card>

      <Sheet
        open={cartOpen}
        title="New order"
        onClose={() => setCartOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCartOpen(false)}>
              Close
            </Button>
            <Button onClick={submitCheckout} disabled={checkout.isPending}>
              {checkout.isPending ? "Placing…" : "Checkout"}
            </Button>
          </>
        }
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={checkout.error} />
          <Card title="Add item">
            <div className="form-row">
              <Field label="Product" error={cartItemErrors.product_id}>
                <SheetSelect
                  value={cartItemForm.product_id}
                  options={productOptions}
                  onChange={(value) => setCartItemForm((prev) => ({ ...prev, product_id: value }))}
                  loading={products.isLoading}
                  placeholder="Search products"
                />
              </Field>
              <Field label="Qty" error={cartItemErrors.qty}>
                <Input
                  value={cartItemForm.qty}
                  onChange={(event) =>
                    setCartItemForm((prev) => ({ ...prev, qty: event.target.value }))
                  }
                />
              </Field>
              <Button onClick={addToCart} disabled={addCartItem.isPending}>
                Add
              </Button>
            </div>
            <ErrorBanner error={addCartItem.error} />
          </Card>

          <Card title="Cart">
            {cart.isLoading ? (
              <div className="muted">Loading…</div>
            ) : cart.data && cart.data.items.length > 0 ? (
              <div className="stack">
                {cart.data.items.map((item) => (
                  <div className="form-row" key={item.id}>
                    <div style={{ flex: 3 }}>
                      {productLabels.get(item.product_id) ?? item.product_id}
                    </div>
                    <Field label="Qty">
                      <Input
                        value={qtyDrafts[item.id] ?? item.qty}
                        onChange={(event) =>
                          setQtyDrafts((prev) => ({ ...prev, [item.id]: event.target.value }))
                        }
                      />
                    </Field>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        updateCartItem.mutate({
                          itemId: item.id,
                          qty: qtyDrafts[item.id] ?? item.qty,
                        })
                      }
                      disabled={updateCartItem.isPending}
                    >
                      Save
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => removeCartItem.mutate(item.id)}
                      disabled={removeCartItem.isPending}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Cart is empty" message="Add a product to begin." />
            )}
          </Card>

          <Card title="Checkout">
            <Field label="Customer" error={checkoutErrors.customer_id}>
              <SheetSelect
                value={checkoutForm.customer_id}
                options={customerOptions}
                onChange={(value) => setCheckoutForm((prev) => ({ ...prev, customer_id: value }))}
                loading={customers.isLoading}
              />
            </Field>
            <div className="grid-2">
              <Field label="Shipping address" error={checkoutErrors.shipping_address}>
                <Input
                  value={checkoutForm.shipping_address ?? ""}
                  onChange={(event) =>
                    setCheckoutForm((prev) => ({ ...prev, shipping_address: event.target.value }))
                  }
                />
              </Field>
              <Field label="Billing address" error={checkoutErrors.billing_address}>
                <Input
                  value={checkoutForm.billing_address ?? ""}
                  onChange={(event) =>
                    setCheckoutForm((prev) => ({ ...prev, billing_address: event.target.value }))
                  }
                />
              </Field>
            </div>
            <div className="grid-2">
              <Field label="Shipping total" error={checkoutErrors.shipping_total}>
                <Input
                  value={checkoutForm.shipping_total ?? "0"}
                  onChange={(event) =>
                    setCheckoutForm((prev) => ({ ...prev, shipping_total: event.target.value }))
                  }
                />
              </Field>
              <Field label="Notes" error={checkoutErrors.notes}>
                <Input
                  value={checkoutForm.notes ?? ""}
                  onChange={(event) =>
                    setCheckoutForm((prev) => ({ ...prev, notes: event.target.value }))
                  }
                />
              </Field>
            </div>
            {activeQuote ? (
              <div className="stack">
                <div className="toolbar" style={{ justifyContent: "space-between" }}>
                  <span className="muted">Subtotal</span>
                  <span>{formatMoney(activeQuote.subtotal, activeQuote.currency)}</span>
                </div>
                <div className="toolbar" style={{ justifyContent: "space-between" }}>
                  <span className="muted">Tax</span>
                  <span>{formatMoney(activeQuote.tax_total, activeQuote.currency)}</span>
                </div>
                <div className="toolbar" style={{ justifyContent: "space-between" }}>
                  <span className="muted">Shipping</span>
                  <span>{formatMoney(activeQuote.shipping_total, activeQuote.currency)}</span>
                </div>
                <div className="toolbar" style={{ justifyContent: "space-between" }}>
                  <strong>Total</strong>
                  <strong>{formatMoney(activeQuote.total, activeQuote.currency)}</strong>
                </div>
              </div>
            ) : null}
          </Card>
        </div>
      </Sheet>

      <Sheet
        open={selectedOrderId !== null}
        title={detailOrder ? detailOrder.doc_number : "Order"}
        onClose={() => {
          setSelectedOrderId(null);
          setPayForm(EMPTY_PAY);
          setPayErrors({});
        }}
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={detail.error} />
          {detail.isLoading ? <div className="muted">Loading…</div> : null}
          {detailOrder ? (
            <div className="stack">
              <div className="grid-2">
                <div>
                  <div className="muted">Status</div>
                  <StatusBadge status={detailOrder.status} />
                </div>
                <div>
                  <div className="muted">Payment</div>
                  <StatusBadge status={detailOrder.payment_state} />
                </div>
                <div>
                  <div className="muted">Date</div>
                  <div>{formatDate(detailOrder.order_date)}</div>
                </div>
                <div>
                  <div className="muted">Total</div>
                  <div>{formatMoney(detailOrder.total, detailOrder.currency)}</div>
                </div>
              </div>
              <Card title="Lines">
                <DataTable
                  columns={lineColumns}
                  rows={detailOrder.lines}
                  rowKey={(l) => l.id}
                  empty={<EmptyState title="No lines" />}
                />
              </Card>

              <ErrorBanner error={payOrder.error} />
              <ErrorBanner error={cancelOrder.error} />

              {detailOrder.status === "pending_payment" ? (
                <Card title="Payment">
                  <div className="grid-2">
                    <Field label="Method" error={payErrors.method}>
                      <SheetSelect
                        value={payForm.method}
                        options={PAY_METHOD_OPTIONS}
                        onChange={(value) => setPayForm((prev) => ({ ...prev, method: value }))}
                      />
                    </Field>
                    <Field label="Provider" error={payErrors.provider}>
                      <Input
                        value={payForm.provider}
                        onChange={(event) =>
                          setPayForm((prev) => ({ ...prev, provider: event.target.value }))
                        }
                      />
                    </Field>
                  </div>
                  <Button onClick={submitPay} disabled={payOrder.isPending}>
                    {payOrder.isPending ? "Processing…" : "Pay"}
                  </Button>
                </Card>
              ) : null}

              {detailOrder.status !== "cancelled" && detailOrder.payment_state !== "paid" ? (
                <Button
                  variant="danger"
                  onClick={() => cancelOrder.mutate(detailOrder.id)}
                  disabled={cancelOrder.isPending}
                >
                  {cancelOrder.isPending ? "Cancelling…" : "Cancel order"}
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </Sheet>
    </>
  );
}
