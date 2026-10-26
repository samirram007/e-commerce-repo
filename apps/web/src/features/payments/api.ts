import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  allocationSchema,
  customerSchema,
  paymentSchema,
  vendorSchema,
  type Allocation,
  type Customer,
  type Payment,
  type PaymentCreateInput,
  type Vendor,
} from "./schemas";

export async function fetchPayments(): Promise<Payment[]> {
  const { data } = await api.get("/payments");
  return z.array(paymentSchema).parse(data);
}

export async function createPayment(input: PaymentCreateInput): Promise<Payment> {
  const { data } = await api.post("/payments", input);
  return paymentSchema.parse(data);
}

export async function fetchAllocations(paymentId: string): Promise<Allocation[]> {
  const { data } = await api.get(`/payments/${paymentId}/allocations`);
  return z.array(allocationSchema).parse(data);
}

export async function fetchCustomers(): Promise<Customer[]> {
  const { data } = await api.get("/partners/customers");
  return z.array(customerSchema).parse(data);
}

export async function fetchVendors(): Promise<Vendor[]> {
  const { data } = await api.get("/partners/vendors");
  return z.array(vendorSchema).parse(data);
}
