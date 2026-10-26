import { useQuery } from "@tanstack/react-query";
import { interestsQueryOptions } from "./queries";
import { ProductCard } from "./ProductCard";
import { EmptyState, Spinner, Tabs } from "../../components/ui";
import { useState } from "react";

type Tab = "favorite" | "watchlist";

export function InterestsPage() {
  const [tab, setTab] = useState<Tab>("favorite");
  const interests = useQuery(interestsQueryOptions());

  if (interests.isLoading) return <Spinner />;
  if (interests.isError) return <EmptyState title="Could not load wishlist" />;

  const items = tab === "favorite" ? interests.data?.favorite ?? [] : interests.data?.watchlist ?? [];

  return (
    <div className="shop-page">
      <h1 className="page-title">Wishlist</h1>
      <Tabs
        tabs={[
          { key: "favorite", label: `Favorites (${interests.data?.favorite?.length ?? 0})` },
          { key: "watchlist", label: `Watchlist (${interests.data?.watchlist?.length ?? 0})` },
        ]}
        active={tab}
        onChange={(v) => setTab(v as Tab)}
      />
      {items.length === 0 ? (
        <EmptyState title={tab === "favorite" ? "No favorites yet" : "Watchlist is empty"} />
      ) : (
        <div className="shop-product-grid">
          {items.map((p) => (
            <ProductCard key={p.id} product={p} showInterest />
          ))}
        </div>
      )}
    </div>
  );
}