import { createFileRoute } from "@tanstack/react-router";
import { PolicyPage } from "../../features/storefront/InfoPages";

export const Route = createFileRoute("/_shop/policies/$slug")({
  component: function PolicyRoute() {
    return <PolicyPage slug={Route.useParams().slug} />;
  },
});
