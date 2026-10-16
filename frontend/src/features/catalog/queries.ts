import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCategory,
  createProduct,
  createUom,
  fetchCategories,
  fetchProducts,
  fetchUoms,
  updateProduct,
} from "./api";
import type { ProductPayload } from "./schemas";

export interface ProductFilters {
  search?: string;
  categoryId?: string;
}

export const catalogKeys = {
  all: ["catalog"] as const,
  products: (filters: ProductFilters) => [...catalogKeys.all, "products", filters] as const,
  categories: () => [...catalogKeys.all, "categories"] as const,
  uoms: () => [...catalogKeys.all, "uoms"] as const,
};

export function productsQueryOptions(filters: ProductFilters = {}) {
  return queryOptions({
    queryKey: catalogKeys.products(filters),
    queryFn: () => fetchProducts(filters),
  });
}

export function categoriesQueryOptions() {
  return queryOptions({
    queryKey: catalogKeys.categories(),
    queryFn: fetchCategories,
    staleTime: 5 * 60_000,
  });
}

export function uomsQueryOptions() {
  return queryOptions({
    queryKey: catalogKeys.uoms(),
    queryFn: fetchUoms,
    staleTime: 5 * 60_000,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProductPayload) => createProduct(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKeys.all }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Record<string, unknown> }) =>
      updateProduct(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKeys.all }),
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; parent_id?: string | null }) => createCategory(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKeys.categories() }),
  });
}

export function useCreateUom() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { code: string; name: string }) => createUom(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKeys.uoms() }),
  });
}
