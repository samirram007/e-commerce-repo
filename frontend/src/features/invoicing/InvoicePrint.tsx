import { formatDate, formatMoney, formatQty, formatRate, gstLabel, splitTaxAmount } from "../../lib/format";
import type { Invoice, InvoiceLine } from "./schemas";

export interface InvoiceCompany {
  name: string;
  legal_name?: string | null;
  address?: string | null;
  tax_identifier?: string | null;
}

/**
 * Printable GST tax invoice: seller/buyer GSTIN, taxable value per slab and the
 * CGST/SGST split of each slab's tax. The browser's print dialog renders this
 * block on its own (see the `@media print` rules for `.invoice-print`).
 */
export function InvoicePrint({
  invoice,
  lines,
  company,
}: {
  invoice: Invoice;
  lines: InvoiceLine[];
  company: InvoiceCompany | null;
}) {
  const slabs = invoice.tax_breakup ?? [];
  const slabTotals = slabs.reduce(
    (acc, slab) => {
      const { cgst, sgst } = splitTaxAmount(slab.amount);
      acc.taxable += Number(slab.taxable);
      acc.cgst += cgst;
      acc.sgst += sgst;
      return acc;
    },
    { taxable: 0, cgst: 0, sgst: 0 },
  );
  const taxableValue = slabs.length
    ? slabTotals.taxable
    : Number(invoice.subtotal) - Number(invoice.discount_total);
  const hasDiscount = Number(invoice.discount_total) > 0;

  return (
    <div className="invoice-print">
      <header className="invoice-print-head">
        <div>
          <h2 className="invoice-print-store">{company?.legal_name || company?.name || "Store"}</h2>
          {company?.address ? <p className="muted">{company.address}</p> : null}
          <p className="muted">
            GSTIN: {company?.tax_identifier ? <strong>{company.tax_identifier}</strong> : "Not registered"}
          </p>
        </div>
        <div className="invoice-print-meta">
          <h3>TAX INVOICE</h3>
          <p>
            <strong>{invoice.doc_number}</strong>
          </p>
          <p className="muted">Date: {formatDate(invoice.invoice_date)}</p>
          {invoice.due_date ? <p className="muted">Due: {formatDate(invoice.due_date)}</p> : null}
          <p className="muted">Status: {invoice.status}</p>
        </div>
      </header>

      <section className="invoice-print-party">
        <div>
          <div className="muted">Billed to</div>
          <div>
            <strong>{invoice.customer_name}</strong>
          </div>
          {invoice.customer_address ? (
            <div className="invoice-print-address">{invoice.customer_address}</div>
          ) : null}
          <div className="muted">
            GSTIN: {invoice.customer_tax_identifier ?? "Unregistered"}
          </div>
        </div>
        <div>
          <div className="muted">Currency</div>
          <div>{invoice.currency}</div>
        </div>
      </section>

      <table className="invoice-print-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Description</th>
            <th>HSN/SAC</th>
            <th className="num">Qty</th>
            <th className="num">Rate</th>
            <th className="num">Taxable value</th>
            <th className="num">GST</th>
            <th className="num">Tax</th>
            <th className="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => (
            <tr key={line.id}>
              <td>{index + 1}</td>
              <td>
                {line.description_snapshot}
                {line.sku_snapshot ? <div className="muted">{line.sku_snapshot}</div> : null}
              </td>
              <td>{line.hsn_sac ?? "—"}</td>
              <td className="num">{formatQty(line.qty)}</td>
              <td className="num">{formatMoney(line.unit_price, invoice.currency)}</td>
              <td className="num">
                {formatMoney(Number(line.line_total) - Number(line.tax_amount), invoice.currency)}
              </td>
              <td className="num">{formatRate(line.tax_percentage)}%</td>
              <td className="num">{formatMoney(line.tax_amount, invoice.currency)}</td>
              <td className="num">{formatMoney(line.line_total, invoice.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {slabs.length > 0 ? (
        <table className="invoice-print-table invoice-print-slab">
          <thead>
            <tr>
              <th>GST slab</th>
              <th className="num">Taxable value</th>
              <th className="num">CGST</th>
              <th className="num">SGST</th>
              <th className="num">Total tax</th>
            </tr>
          </thead>
          <tbody>
            {slabs.map((slab) => {
              const { cgst, sgst } = splitTaxAmount(slab.amount);
              return (
                <tr key={slab.rate}>
                  <td>{gstLabel(slab.rate)}</td>
                  <td className="num">{formatMoney(slab.taxable, invoice.currency)}</td>
                  <td className="num">{formatMoney(cgst, invoice.currency)}</td>
                  <td className="num">{formatMoney(sgst, invoice.currency)}</td>
                  <td className="num">{formatMoney(slab.amount, invoice.currency)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}

      <section className="invoice-print-totals">
        {hasDiscount ? (
          <>
            <div>
              <span className="muted">Subtotal</span>
              <span>{formatMoney(invoice.subtotal, invoice.currency)}</span>
            </div>
            <div>
              <span className="muted">Discount</span>
              <span>-{formatMoney(invoice.discount_total, invoice.currency)}</span>
            </div>
          </>
        ) : null}
        <div>
          <span className="muted">Taxable value</span>
          <span>{formatMoney(taxableValue, invoice.currency)}</span>
        </div>
        <div>
          <span className="muted">CGST</span>
          <span>{formatMoney(slabTotals.cgst, invoice.currency)}</span>
        </div>
        <div>
          <span className="muted">SGST</span>
          <span>{formatMoney(slabTotals.sgst, invoice.currency)}</span>
        </div>
        {Number(invoice.shipping_total) > 0 ? (
          <div>
            <span className="muted">Shipping</span>
            <span>{formatMoney(invoice.shipping_total, invoice.currency)}</span>
          </div>
        ) : null}
        <div className="invoice-print-total">
          <span>Total</span>
          <span>{formatMoney(invoice.total, invoice.currency)}</span>
        </div>
      </section>

      <footer className="invoice-print-foot muted">
        Computer-generated tax invoice — amounts in {invoice.currency}. Taxable value excludes GST.
      </footer>
    </div>
  );
}
