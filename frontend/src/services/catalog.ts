import { api } from "../lib/api-client";

// ---- product ----
export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  stock_type: string;
  base_cost: string;
  base_price: string;
  is_active: boolean;
  is_sellable: boolean;
  is_purchasable: boolean;
}

export async function listProducts(search?: string): Promise<Product[]> {
  const { data } = await api.get("/catalog/products", { params: { search } });
  return data.items ?? [];
}

export async function createProduct(input: Record<string, unknown>): Promise<Product> {
  const { data } = await api.post<Product>("/catalog/products", input);
  return data;
}

// ---- partners ----
export interface Partner {
  id: string;
  code: string;
  name: string;
  email: string | null;
}

export async function listPartners(kind: "customers" | "vendors", search?: string): Promise<Partner[]> {
  const { data } = await api.get<Partner[]>(`/partners/${kind}`, { params: { search } });
  return data;
}

export async function createPartner(kind: "customers" | "vendors", input: { code: string; name: string }): Promise<Partner> {
  const { data } = await api.post<Partner>(`/partners/${kind}`, input);
  return data;
}
