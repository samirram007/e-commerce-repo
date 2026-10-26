import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  cancelRun,
  createEmployee,
  createRun,
  fetchEmployees,
  fetchRun,
  fetchRuns,
  postRun,
  updateEmployee,
} from "./api";
import type { ListState } from "../../hooks/use-list-state";
import { listQueryKey } from "../../hooks/use-list-state";
import type { EmployeePayload, EmployeeUpdatePayload, RunCreatePayload } from "./schemas";

export const payrollKeys = {
  all: ["payroll"] as const,
  employees: (list: ListState) => [...payrollKeys.all, "employees", ...listQueryKey(list)] as const,
  runs: () => [...payrollKeys.all, "runs"] as const,
  run: (id: string) => [...payrollKeys.all, "run", id] as const,
};

export function runsQueryOptions() {
  return queryOptions({ queryKey: payrollKeys.runs(), queryFn: fetchRuns });
}

export function runQueryOptions(id: string) {
  return queryOptions({
    queryKey: payrollKeys.run(id),
    queryFn: () => fetchRun(id),
    enabled: Boolean(id),
  });
}

/** Run mutations refresh both the list and any open detail view. */
function invalidateRuns(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: payrollKeys.runs() });
  void queryClient.invalidateQueries({ queryKey: [...payrollKeys.all, "run"] });
}

export function useCreateRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RunCreatePayload) => createRun(input),
    onSuccess: () => invalidateRuns(queryClient),
  });
}

export function usePostRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => postRun(id),
    onSuccess: () => invalidateRuns(queryClient),
  });
}

export function useCancelRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelRun(id),
    onSuccess: () => invalidateRuns(queryClient),
  });
}

/**
 * List query options. The key includes every server-side param (page, sort,
 * search, filters), so each view is cached separately and invalidated together
 * under `payrollKeys.all` after a mutation.
 */
export function employeesQueryOptions(list: ListState) {
  return queryOptions({
    queryKey: payrollKeys.employees(list),
    queryFn: () => fetchEmployees({
      page: list.page,
      page_size: list.pageSize,
      ...(list.search.trim() ? { search: list.search.trim() } : {}),
      ...(list.sort ? { sort: list.sort, order: list.order } : {}),
      ...Object.fromEntries(
        Object.entries(list.filters).filter(([, v]) => v !== ""),
      ),
    }),
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EmployeePayload) => createEmployee(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

export function useUpdateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: EmployeeUpdatePayload }) =>
      updateEmployee(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}
