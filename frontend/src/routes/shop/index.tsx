import { createFileRoute } from "@tanstack/react-router";
import { HomePage } from "../../features/storefront/HomePage";

export const Route = createFileRoute("/shop/")({
  component: HomePage,
});