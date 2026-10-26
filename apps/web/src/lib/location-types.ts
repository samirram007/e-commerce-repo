/**
 * Storage location types (mirrors the backend `LOCATION_TYPE_RANKS`).
 *
 * A location's type determines its rank; a child must have a strictly greater
 * rank than its parent. Facility types (rank 0) may be a root. Only stockable
 * types may hold stock.
 */
export const LOCATION_TYPES = [
  // facilities / sites — may be a root (no parent)
  "warehouse",
  "godown",
  "store",
  "depot",
  "branch",
  "showroom",
  "outlet",
  "yard",
  "cold_storage",
  "bonded",
  "transit",
  "quarantine",
  "scrap",
  // internal structure (deepest last)
  "floor",
  "zone",
  "aisle",
  "rack",
  "shelf",
  "bin",
] as const;
export type LocationType = (typeof LOCATION_TYPES)[number];

/** Type → rank. Lower is closer to the root. */
export const LOCATION_TYPE_RANKS: Record<LocationType, number> = {
  warehouse: 0,
  godown: 0,
  store: 0,
  depot: 0,
  branch: 0,
  showroom: 0,
  outlet: 0,
  yard: 0,
  cold_storage: 0,
  bonded: 0,
  transit: 0,
  quarantine: 0,
  scrap: 0,
  floor: 1,
  zone: 1,
  aisle: 2,
  rack: 3,
  shelf: 4,
  bin: 5,
};

/** Facility types may be a root location. */
export const FACILITY_TYPES: readonly LocationType[] = LOCATION_TYPES.filter(
  (type) => LOCATION_TYPE_RANKS[type] === 0,
);

/** Types that may physically hold stock. */
export const STOCKABLE_TYPES: readonly LocationType[] = LOCATION_TYPES.filter(
  (type) => type === "bin",
);

export function isFacilityType(type: string): boolean {
  return (FACILITY_TYPES as readonly string[]).includes(type);
}

export function isStockableType(type: string): boolean {
  return (STOCKABLE_TYPES as readonly string[]).includes(type);
}

/** Rank of a location type, or -1 when unknown. */
export function locationRank(type: string): number {
  return (LOCATION_TYPE_RANKS as Record<string, number>)[type] ?? -1;
}
