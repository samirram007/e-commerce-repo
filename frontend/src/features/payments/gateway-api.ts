import { api } from "../../lib/api-client";
import {
  gatewayPageSchema,
  gatewaySchema,
  type Gateway,
  type GatewayPayload,
  type GatewayPage,
} from "./gateway-schemas";

/** Provider catalog + this company's configuration for every gateway. */
export async function fetchGateways(): Promise<GatewayPage> {
  const { data } = await api.get("/payments/gateways");
  return gatewayPageSchema.parse(data);
}

/** Enable/disable a gateway and store its credentials and checkout options. */
export async function saveGateway(provider: string, input: GatewayPayload): Promise<Gateway> {
  const { data } = await api.put(`/payments/gateways/${provider}`, input);
  return gatewaySchema.parse(data);
}

/** Remove a company's configuration for one provider (stored secrets included). */
export async function deleteGateway(provider: string): Promise<void> {
  await api.delete(`/payments/gateways/${provider}`);
}
