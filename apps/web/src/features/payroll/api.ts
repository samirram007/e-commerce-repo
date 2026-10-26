import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  employeePageSchema,
  employeeSchema,
  payrollRunDetailSchema,
  type Employee,
  type EmployeePayload,
  type EmployeeUpdatePayload,
  type PayrollRun,
  type PayrollRunDetail,
  type RunCreatePayload,
} from "./schemas";

/**
 * Server-side list: `params` comes from `useListState().params`
 * ({page, page_size, search, sort, order, employment_status}).
 */
export async function fetchEmployees(
  params: Record<string, string | number>,
): Promise<z.infer<typeof employeePageSchema>> {
  const { data } = await api.get("/payroll/employees", { params });
  return employeePageSchema.parse(data);
}

export async function createEmployee(input: EmployeePayload): Promise<Employee> {
  const { data } = await api.post("/payroll/employees", input);
  return employeeSchema.parse(data);
}

export async function updateEmployee(
  id: string,
  input: EmployeeUpdatePayload,
): Promise<Employee> {
  const { data } = await api.patch(`/payroll/employees/${id}`, input);
  return employeeSchema.parse(data);
}

/* ---- payroll runs / payslips ---- */

export async function fetchRuns(): Promise<PayrollRun[]> {
  const { data } = await api.get("/payroll/runs");
  return z.array(payrollRunDetailSchema.omit({ payslips: true })).parse(data);
}

export async function fetchRun(id: string): Promise<PayrollRunDetail> {
  const { data } = await api.get(`/payroll/runs/${id}`);
  return payrollRunDetailSchema.parse(data);
}

export async function createRun(input: RunCreatePayload): Promise<PayrollRunDetail> {
  const { data } = await api.post("/payroll/runs", input);
  return payrollRunDetailSchema.parse(data);
}

export async function postRun(id: string): Promise<PayrollRunDetail> {
  const { data } = await api.post(`/payroll/runs/${id}/post`);
  return payrollRunDetailSchema.parse(data);
}

export async function cancelRun(id: string): Promise<PayrollRunDetail> {
  const { data } = await api.post(`/payroll/runs/${id}/cancel`);
  return payrollRunDetailSchema.parse(data);
}
