import { useState } from "react";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type RangeKey = "today" | "yesterday" | "7d" | "30d" | "90d" | "custom";

export interface DateRangeValue {
  key: RangeKey;
  from?: string;
  to?: string;
}

const PRESETS: { key: RangeKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
];

/**
 * The shared range picker.
 *
 * One component so every widget on a page asks the API for the same window —
 * the previous dashboard had each widget doing its own date maths, and they
 * could disagree about what "last 7 days" meant.
 */
export function DateRangeFilter({
  value,
  onChange,
}: {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
}) {
  const [showCustom, setShowCustom] = useState(value.key === "custom");

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        className="flex items-center gap-1 rounded-xl p-1"
        style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
      >
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            onClick={() => {
              setShowCustom(false);
              onChange({ key: preset.key });
            }}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-colors",
              value.key === preset.key && "bg-purple-500/20 text-purple-300"
            )}
            style={value.key === preset.key ? undefined : { color: "var(--page-text-secondary)" }}
          >
            {preset.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom((v) => !v)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors",
            value.key === "custom" && "bg-purple-500/20 text-purple-300"
          )}
          style={value.key === "custom" ? undefined : { color: "var(--page-text-secondary)" }}
        >
          <CalendarIcon className="w-3.5 h-3.5" />
          Custom
        </button>
      </div>

      {showCustom && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={value.from ?? ""}
            onChange={(e) => onChange({ ...value, key: "custom", from: e.target.value })}
            className="px-2.5 py-1.5 rounded-lg text-xs"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
          <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>to</span>
          <input
            type="date"
            value={value.to ?? ""}
            onChange={(e) => onChange({ ...value, key: "custom", to: e.target.value })}
            className="px-2.5 py-1.5 rounded-lg text-xs"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
        </div>
      )}
    </div>
  );
}

export function rangeQuery(value: DateRangeValue): string {
  const params = new URLSearchParams({ range: value.key });
  // A custom range with only one end is incomplete; sending it would 400.
  if (value.key === "custom" && value.from && value.to) {
    params.set("from", value.from);
    params.set("to", value.to);
  }
  return params.toString();
}

export default DateRangeFilter;
