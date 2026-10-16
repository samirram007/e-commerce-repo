import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  addressSchema,
  customerSchema,
  type Address,
  type AddressPayload,
  type Customer,
  type PartnerCreatePayload,
  type PartnerUpdatePayload,
  vendorSchema,
  type Vendor,
} from "./schemas";

export async function fetchCustomers(search?: string): Promise<Customer[]> {
  const { data } = await api.get("/partners/customers", {
    params: { search: search || undefined },
  });
  return z.array(customerSchema).parse(data);
}

export async function createCustomer(input: PartnerCreatePayload): Promise<Customer> {
  const { data } = await api.post("/partners/customers", input);
  return customerSchema.parse(data);
}

export async function updateCustomer(
  id: string,
  input: PartnerUpdatePayload,
): Promise<Customer> {
  const { data } = await api.patch(`/partners/customers/${id}`, input);
  return customerSchema.parse(data);
}

export async function fetchVendors(search?: string): Promise<Vendor[]> {
  const { data } = await api.get("/partners/vendors", {
    params: { search: search || undefined },
  });
  return z.array(vendorSchema).parse(data);
}

export async function createVendor(input: PartnerCreatePayload): Promise<Vendor> {
  const { data } = await api.post("/partners/vendors", input);
  return vendorSchema.parse(data);
}

export async function updateVendor(id: string, input: PartnerUpdatePayload): Promise<Vendor> {
  const { data } = await api.patch(`/partners/vendors/${id}`, input);
  return vendorSchema.parse(data);
}

export async function fetchAddresses(partnerType: string, partnerId: string): Promise<Address[]> {
  const { data } = await api.get("/partners/addresses", {
    params: { partner_type: partnerType, partner_id: partnerId },
  });
  return z.array(addressSchema).parse(data);
}

export async function createAddress(
  partnerType: string,
  partnerId: string,
  input: AddressPayload,
): Promise<Address> {
  const { data } = await api.post("/partners/addresses", input, {
    params: { partner_type: partnerType, partner_id: partnerId },
  });
  return addressSchema.parse(data);
}
