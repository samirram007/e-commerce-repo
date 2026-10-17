import { useMemo } from "react";
import { SheetSelect, type SheetOption } from "../../components/sheet";
import { formatDate } from "../../lib/format";
import { ALL_PERIODS, usePeriodContext } from "./period-context";

/**
 * Topbar control that lets the signed-in user switch the active fiscal year.
 *
 * The selection is user-wise and persisted server-side, so it follows the user
 * across reloads without changing what other users of the company see.
 */
export function FiscalYearPicker(): React.JSX.Element {
  const { fiscalYear, fiscalYears, isLoading, isSwitching, setFiscalYear } = usePeriodContext();

  const options = useMemo<SheetOption[]>(() => {
    const items: SheetOption[] = [
      { value: ALL_PERIODS, label: "All periods", hint: "No fiscal-year filter" },
    ];
    for (const fy of fiscalYears) {
      items.push({
        value: fy.id,
        label: fy.name?.trim() ? fy.name : `${fy.start_date} → ${fy.end_date}`,
        hint: `${formatDate(fy.start_date)} → ${formatDate(fy.end_date)}${fy.is_open ? "" : " · closed"}`,
      });
    }
    return items;
  }, [fiscalYears]);

  return (
    <SheetSelect
      value={fiscalYear?.id ?? ALL_PERIODS}
      options={options}
      onChange={setFiscalYear}
      placeholder={isLoading ? "Loading…" : "All periods"}
      title="Switch fiscal year"
      searchPlaceholder="Search fiscal years…"
      loading={isLoading}
      disabled={isSwitching}
      emptyText="No fiscal years defined"
      className="fiscal-year-switcher"
    />
  );
}
