import { useState } from "react";
import { PageHeader, Tabs } from "../../components/ui";
import { CountsTab } from "./CountsTab";
import { LedgerTab } from "./LedgerTab";
import { AdjustmentsTab, TransfersTab } from "./MovementsTabs";
import { OnHandTab } from "./OnHandTab";
import { ValuationTab } from "./ValuationTab";

type InventoryTab = "on-hand" | "ledger" | "transfers" | "adjustments" | "counts" | "valuation";

export function InventoryPage() {
  const [tab, setTab] = useState<InventoryTab>("on-hand");

  return (
    <>
      <PageHeader
        title="Inventory"
        description="Balances, ledger, movements, counts and valuation"
      />
      <Tabs
        tabs={[
          { key: "on-hand", label: "On hand" },
          { key: "ledger", label: "Ledger" },
          { key: "transfers", label: "Transfers" },
          { key: "adjustments", label: "Adjustments" },
          { key: "counts", label: "Counts" },
          { key: "valuation", label: "Valuation" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as InventoryTab)}
      />

      {tab === "on-hand" ? <OnHandTab /> : null}
      {tab === "ledger" ? <LedgerTab /> : null}
      {tab === "transfers" ? <TransfersTab /> : null}
      {tab === "adjustments" ? <AdjustmentsTab /> : null}
      {tab === "counts" ? <CountsTab /> : null}
      {tab === "valuation" ? <ValuationTab /> : null}
    </>
  );
}
