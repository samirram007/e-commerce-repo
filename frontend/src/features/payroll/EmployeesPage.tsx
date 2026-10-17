import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, PageHeader, StatusBadge } from "../../components/ui";
import { ServerDataTable, type ServerColumn } from "../../components/data-table";
import { CrudFormModal, useCrudForm } from "../../components/crud-form";
import { useListState } from "../../hooks/use-list-state";
import { usePermissions } from "../../hooks/use-permissions";
import { formatMoney, titleCase } from "../../lib/format";
import { employeesQueryOptions, useCreateEmployee, useUpdateEmployee } from "./queries";
import {
  EMPLOYMENT_STATUSES,
  employeeFormSchema,
  type Employee,
  type EmployeeFormInput,
  employeeUpdateSchema,
} from "./schemas";

const EMPTY_FORM: EmployeeFormInput = {
  employee_code: "",
  first_name: "",
  last_name: "",
  email: "",
  job_title: "",
  department: "",
  hire_date: "",
  base_salary: "0",
  allowances: "0",
  deduction_rate: "0",
};

const STATUS_OPTIONS = EMPLOYMENT_STATUSES.map((value) => ({
  value,
  label: titleCase(value),
}));

function formFromEmployee(employee: Employee): EmployeeFormInput {
  return {
    employee_code: employee.employee_code,
    first_name: employee.first_name,
    last_name: employee.last_name,
    email: employee.email ?? "",
    job_title: employee.job_title ?? "",
    department: employee.department ?? "",
    hire_date: employee.hire_date ?? "",
    base_salary: employee.base_salary,
    allowances: employee.allowances,
    deduction_rate: employee.deduction_rate,
  };
}

export function EmployeesPage() {
  const { has } = usePermissions();
  const canManage = has("payroll.manage");

  // One server-side list state: pagination, sort, debounced search, filters.
  const list = useListState({ sort: "employee_code", order: "asc" });
  const employees = useQuery(employeesQueryOptions(list.state));

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);

  const createEmployee = useCreateEmployee();
  const updateEmployee = useUpdateEmployee();
  const mutationError = createEmployee.error ?? updateEmployee.error;

  const form = useCrudForm({
    schema: employeeFormSchema,
    initialValues: EMPTY_FORM,
    onSubmit: (values) => {
      if (editing) {
        const parsed = employeeUpdateSchema.safeParse(values);
        if (!parsed.success) return; // schema already validated the shared fields
        updateEmployee.mutate(
          { id: editing.id, input: parsed.data },
          { onSuccess: () => setModalOpen(false) },
        );
        return;
      }
      createEmployee.mutate(values, { onSuccess: () => setModalOpen(false) });
    },
  });

  function openCreate() {
    setEditing(null);
    form.reset(EMPTY_FORM);
    setModalOpen(true);
  }

  function openEdit(employee: Employee) {
    setEditing(employee);
    form.reset(formFromEmployee(employee));
    setModalOpen(true);
  }

  const columns: ServerColumn<Employee>[] = [
    { key: "code", header: "Code", sortKey: "employee_code", render: (e) => <strong>{e.employee_code}</strong> },
    { key: "name", header: "Name", sortKey: "first_name", render: (e) => `${e.first_name} ${e.last_name}` },
    { key: "department", header: "Department", sortKey: "department", render: (e) => e.department ?? "—" },
    {
      key: "salary",
      header: "Base salary",
      sortKey: "base_salary",
      align: "right",
      render: (e) => formatMoney(e.base_salary),
    },
    {
      key: "allowances",
      header: "Allowances",
      sortKey: "allowances",
      align: "right",
      render: (e) => formatMoney(e.allowances),
    },
    {
      key: "deduction",
      header: "Deduction %",
      sortKey: "deduction_rate",
      align: "right",
      render: (e) => `${e.deduction_rate}%`,
    },
    {
      key: "status",
      header: "Status",
      sortKey: "employment_status",
      render: (e) => <StatusBadge status={e.employment_status} />,
    },
    {
      key: "actions",
      header: "",
      render: (e) =>
        canManage ? (
          <Button variant="secondary" onClick={() => openEdit(e)}>
            Edit
          </Button>
        ) : null,
    },
  ];

  const formFields = [
    { name: "employee_code", label: "Employee code", placeholder: "E-001", disabled: editing !== null },
    { name: "first_name", label: "First name" },
    { name: "last_name", label: "Last name" },
    { name: "email", label: "Email" },
    { name: "job_title", label: "Job title" },
    { name: "department", label: "Department" },
    { name: "hire_date", label: "Hire date", placeholder: "YYYY-MM-DD" },
    { name: "base_salary", label: "Base salary", type: "money" as const },
    { name: "allowances", label: "Allowances", type: "money" as const },
    { name: "deduction_rate", label: "Deduction %", type: "money" as const },
  ];

  return (
    <>
      <PageHeader
        title="Payroll — Employees"
        description="Employee master data with server-side search, sort and pagination"
        actions={
          canManage ? <Button onClick={openCreate}>New employee</Button> : null
        }
      />

      <Card>
        <ServerDataTable
          columns={columns}
          rows={employees.data?.items}
          rowKey={(e) => e.id}
          list={list}
          total={employees.data?.total}
          loading={employees.isLoading}
          error={employees.error}
          onRetry={() => employees.refetch()}
          searchPlaceholder="Search code, name, email…"
          filters={
            <label className="muted" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              Status
              <select
                value={list.state.filters.employment_status ?? ""}
                onChange={(event) => list.setFilter("employment_status", event.target.value)}
                aria-label="Filter by status"
              >
                <option value="">All</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          }
          empty={
            <div className="empty">
              <div className="empty-title">No employees</div>
              <div className="muted">Add your first employee to run payroll.</div>
              {canManage ? (
                <div style={{ marginTop: 10 }}>
                  <Button onClick={openCreate}>New employee</Button>
                </div>
              ) : null}
            </div>
          }
        />
      </Card>

      <CrudFormModal
        open={modalOpen}
        title={editing ? `Edit ${editing.employee_code}` : "New employee"}
        form={form}
        fields={formFields}
        onClose={() => setModalOpen(false)}
        onSubmit={form.submit}
        submitting={createEmployee.isPending || updateEmployee.isPending}
        error={mutationError}
        wide
        submitLabel={editing ? "Save" : "Create"}
      />
    </>
  );
}
