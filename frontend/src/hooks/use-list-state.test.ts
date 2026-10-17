import { describe, expect, it } from "vitest";
import { initialListState, listQueryKey, toListParams, toggleSort } from "./use-list-state";

describe("toListParams", () => {
  it("always sends page and page_size", () => {
    const state = initialListState();
    expect(toListParams(state)).toEqual({ page: 1, page_size: 25 });
  });

  it("omits empty search and sort", () => {
    const state = { ...initialListState(), search: "   " };
    expect(toListParams(state)).toEqual({ page: 1, page_size: 25 });
  });

  it("trims search and includes sort/order together", () => {
    const state = {
      ...initialListState(),
      search: "  acme  ",
      sort: "base_salary",
      order: "desc" as const,
    };
    expect(toListParams(state)).toEqual({
      page: 1,
      page_size: 25,
      search: "acme",
      sort: "base_salary",
      order: "desc",
    });
  });

  it("passes through non-empty filters and skips empty ones", () => {
    const state = {
      ...initialListState(),
      filters: { employment_status: "active", department: "" },
    };
    const params = toListParams(state);
    expect(params.employment_status).toBe("active");
    expect(params.department).toBeUndefined();
  });
});

describe("toggleSort", () => {
  it("starts asc when clicking a new column", () => {
    const state = { ...initialListState(), sort: null };
    expect(toggleSort(state, "base_salary")).toEqual({
      sort: "base_salary",
      order: "asc",
      page: 1,
    });
  });

  it("flips asc -> desc on the same column", () => {
    const state = { ...initialListState(), sort: "base_salary", order: "asc" as const };
    expect(toggleSort(state, "base_salary")).toEqual({
      sort: "base_salary",
      order: "desc",
      page: 1,
    });
  });

  it("clears sort after desc (three-state cycle)", () => {
    const state = { ...initialListState(), sort: "base_salary", order: "desc" as const };
    expect(toggleSort(state, "base_salary")).toEqual({ sort: null, order: "asc", page: 1 });
  });
});

describe("listQueryKey", () => {
  it("is stable for equal states and differs for different ones", () => {
    const a = { ...initialListState(), search: "x" };
    const b = { ...initialListState(), search: "x" };
    const c = { ...initialListState(), search: "y" };
    expect(listQueryKey(a)).toEqual(listQueryKey(b));
    expect(listQueryKey(a)).not.toEqual(listQueryKey(c));
  });
});
