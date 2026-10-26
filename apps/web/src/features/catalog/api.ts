import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  categorySchema,
  productListSchema,
  productSchema,
  type Category,
  type Product,
  type ProductList,
  type ProductPayload,
  uomSchema,
  type Uom,
} from "./schemas";

export async function fetchProducts(
  params: {
    search?: string;
    categoryId?: string;
    stockType?: string;
    isActive?: string;
  } = {},
): Promise<ProductList> {
  const { data } = await api.get("/catalog/products", {
    params: {
      search: params.search || undefined,
      category_id: params.categoryId || undefined,
      stock_type: params.stockType || undefined,
      is_active: params.isActive || undefined,
    },
  });
  return productListSchema.parse(data);
}

export async function createProduct(input: ProductPayload): Promise<Product> {
  const { data } = await api.post("/catalog/products", input);
  return productSchema.parse(data);
}

export async function updateProduct(id: string, input: Record<string, unknown>): Promise<Product> {
  const { data } = await api.patch(`/catalog/products/${id}`, input);
  return productSchema.parse(data);
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await api.get("/catalog/categories");
  return z.array(categorySchema).parse(data);
}

export async function createCategory(input: {
  name: string;
  parent_id?: string | null;
}): Promise<Category> {
  const { data } = await api.post("/catalog/categories", input);
  return categorySchema.parse(data);
}

export async function fetchUoms(): Promise<Uom[]> {
  const { data } = await api.get("/catalog/uoms");
  return z.array(uomSchema).parse(data);
}

export async function createUom(input: { code: string; name: string }): Promise<Uom> {
  const { data } = await api.post("/catalog/uoms", input);
  return uomSchema.parse(data);
}
