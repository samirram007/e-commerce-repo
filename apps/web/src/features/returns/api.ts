import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  type ReturnCreatePayload,
  type ReturnDetail,
  returnDetailSchema,
  type SalesReturn,
  salesReturnSchema,
} from "./schemas";

export async function fetchReturns(status?: string): Promise<SalesReturn[]> {
  const { data } = await api.get("/returns", {
    params: { status: status || undefined },
  });
  return z.array(salesReturnSchema).parse(data);
}

export async function fetchReturn(id: string): Promise<ReturnDetail> {
  const { data } = await api.get(`/returns/${id}`);
  return returnDetailSchema.parse(data);
}

export async function createReturn(input: ReturnCreatePayload): Promise<SalesReturn> {
  const { data } = await api.post("/returns", input);
  return salesReturnSchema.parse(data);
}

export async function approveReturn(id: string): Promise<SalesReturn> {
  const { data } = await api.post(`/returns/${id}/approve`);
  return salesReturnSchema.parse(data);
}

export async function rejectReturn(id: string): Promise<SalesReturn> {
  const { data } = await api.post(`/returns/${id}/reject`);
  return salesReturnSchema.parse(data);
}

export async function completeReturn(id: string): Promise<SalesReturn> {
  const { data } = await api.post(`/returns/${id}/complete`);
  return salesReturnSchema.parse(data);
}
