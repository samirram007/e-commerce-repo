import { useState } from "react";
import { PageHeader, Tabs } from "../../components/ui";
import { EmployeesPage } from "./EmployeesPage";
import { RunsTab } from "./RunsTab";

type PayrollTab = "employees" | "runs";

const TABS: { key: PayrollTab; label: string }[] = [
  { key: "employees", label: "Employees" },
  { key: "runs", label: "Payroll runs" },
];

export function PayrollPage() {
  const [tab, setTab] = useState<PayrollTab>("employees");
  return (
    <>
      <PageHeader
        title="Payroll"
        description="Employees, monthly payroll runs, payslips and GL posting"
      />
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {tab === "employees" ? <EmployeesPage /> : <RunsTab />}
    </>
  );
}
