import { createFileRoute } from "@tanstack/react-router";
import { InterestsPage } from "../../features/storefront/InterestsPage";

export const Route = createFileRoute("/shop/interests")({
  component: InterestsPage,
});