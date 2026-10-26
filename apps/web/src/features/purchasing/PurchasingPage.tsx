import { useState } from "react";
import { PageHeader, Tabs } from "../../components/ui";
import { PurchaseOrdersTab } from "./PurchaseOrdersTab";
import { VendorBillsTab } from "./VendorBillsTab";

type PurchasingTab = "orders" | "bills";

export function PurchasingPage() {
  const [tab, setTab] = useState<PurchasingTab>("orders");

  return (
    <>
      <PageHeader
        title="Purchasing"
        description="Purchase orders, goods receipts and vendor bills"
      />
      <Tabs
        tabs={[
          { key: "orders", label: "Purchase orders" },
          { key: "bills", label: "Vendor bills" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as PurchasingTab)}
      />

      {tab === "orders" ? <PurchaseOrdersTab /> : <VendorBillsTab />}
    </>
  );
}
