import { z } from "zod";

/** Decimal strings from the API (Pydantic v2 JSON), like partners/schemas.ts. */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const EMPLOYMENT_STATUSES = ["active", "inactive"] as const;
export type EmploymentStatus = (typeof EMPLOYMENT_STATUSES)[number];

export const employeeSchema = z.object({
  id: z.string(),
  employee_code: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  email: z.string().nullable(),
  job_title: z.string().nullable(),
  department: z.string().nullable(),
  hire_date: z.string().nullable(),
  employment_status: z.enum(EMPLOYMENT_STATUSES),
  base_salary: decimalString,
  allowances: decimalString,
  deduction_rate: decimalString,
});
export type Employee = z.infer<typeof employeeSchema>;

/** Paginated envelope from app.shared.pagination.Page. */
export const employeePageSchema = z.object({
  items: z.array(employeeSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type EmployeePage = z.infer<typeof employeePageSchema>;

const moneyInput = z
  .string()
  .trim()
  .regex(/^\d+(\.\d{1,2})?$/, "Enter a valid amount")
  .transform((value) => Number(value));

const rateInput = z
  .string()
  .trim()
  .regex(/^\d{1,3}(\.\d{1,2})?$/, "Enter a rate 0–100")
  .transform((value) => Number(value));

const optionalText = (max: number) => z.string().trim().max(max).optional();

export const employeeFormSchema = z.object({
  employee_code: z.string().trim().min(1, "Code is required").max(32),
  first_name: z.string().trim().min(1, "First name is required").max(100),
  last_name: z.string().trim().min(1, "Last name is required").max(100),
  email: optionalText(255),
  job_title: optionalText(120),
  department: optionalText(120),
  hire_date: optionalText(10),
  base_salary: moneyInput,
  allowances: moneyInput,
  deduction_rate: rateInput,
});
export type EmployeeFormInput = z.input<typeof employeeFormSchema>;
export type EmployeePayload = z.output<typeof employeeFormSchema>;

/** Update payload: the backend ignores employee_code on PATCH. */
export const employeeUpdateSchema = employeeFormSchema.omit({ employee_code: true });
export type EmployeeUpdatePayload = z.output<typeof employeeUpdateSchema>;

/* ---- payroll runs / payslips ---- */

export const RUN_STATUSES = ["draft", "posted", "cancelled"] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export const payslipSchema = z.object({
  id: z.string(),
  employee_id: z.string(),
  employee_code: z.string(),
  employee_name: z.string(),
  status: z.string(),
  base_salary: decimalString,
  allowances: decimalString,
  gross: decimalString,
  deduction_rate: decimalString,
  deductions: decimalString,
  net_pay: decimalString,
});
export type Payslip = z.infer<typeof payslipSchema>;

export const payrollRunSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  period_year: z.number(),
  period_month: z.number(),
  status: z.string(),
  employee_count: z.number(),
  total_gross: decimalString,
  total_deductions: decimalString,
  total_net: decimalString,
  journal_entry_id: z.string().nullable(),
  posted_at: z.string().nullable(),
});
export type PayrollRun = z.infer<typeof payrollRunSchema>;

export const payrollRunDetailSchema = payrollRunSchema.extend({
  payslips: z.array(payslipSchema),
});
export type PayrollRunDetail = z.infer<typeof payrollRunDetailSchema>;

export const runCreateFormSchema = z.object({
  period_year: z
    .string()
    .trim()
    .regex(/^\d{4}$/, "Enter a 4-digit year")
    .transform((value) => Number(value)),
  period_month: z
    .enum(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"])
    .transform((value) => Number(value)),
});
export type RunCreateFormInput = z.input<typeof runCreateFormSchema>;
export type RunCreatePayload = z.output<typeof runCreateFormSchema>;

export const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;
