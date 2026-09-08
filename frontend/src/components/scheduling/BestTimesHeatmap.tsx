/**
 * The weekday x hour heatmap, as a calendar overlay.
 *
 * Three visual states, deliberately distinct: a measured cell is tinted by how
 * well it did, a slot never tried is left blank, and when the account has too
 * little history the whole grid is dimmed and captioned as conventions. A
 * viewer must never have to guess which of the three they are looking at.
 */
import { useEffect, useMemo, useState } from "react";
import { Info } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { cn } from "@/lib/utils";
import {
  fetchBestTimes, intensity, WEEKDAY_SHORT, type BestTimes,
} from "@/lib/bestTimes";

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

export function BestTimesHeatmap({
  accountId,
  socialAccountId,
}: {
  accountId: string | null;
  socialAccountId?: string | null;
}) {
  const [data, setData] = useState<BestTimes | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    fetchBestTimes(accountId, socialAccountId)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [accountId, socialAccountId]);

  const { grid, best } = useMemo(() => {
    const lookup = new Map<string, (typeof data extends null ? never : BestTimes)["heatmap"][number]>();
    let peak = 0;
    for (const cell of data?.heatmap ?? []) {
      lookup.set(`${cell.weekday}-${cell.hour}`, cell);
      if (cell.observed && cell.score !== null) peak = Math.max(peak, cell.score);
    }
    return { grid: lookup, best: peak };
  }, [data]);

  if (error || !data) {
    return (
      <GlassCard>
        <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
          {error ? "Could not load posting times." : "Loading…"}
        </p>
      </GlassCard>
    );
  }

  const measured = data.source === "observed";

  return (
    <GlassCard>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
          When your posts do well
        </h3>
        <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
          {data.scope.timezone}
        </span>
      </div>

      {!measured && (
        <p
          className="mb-3 flex items-start gap-1.5 rounded-lg px-3 py-2 text-xs"
          style={{
            backgroundColor: "rgba(245,158,11,0.10)",
            border: "1px solid rgba(245,158,11,0.28)",
            color: "var(--page-text)",
          }}
        >
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#f59e0b" }} />
          {data.explanation}
        </p>
      )}

      <div className={cn("overflow-x-auto", !measured && "opacity-40")}>
        <table className="w-full min-w-[640px] border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th />
              {HOURS.map((hour) => (
                <th key={hour} className="text-[9px] font-normal"
                    style={{ color: "var(--page-text-muted)" }}>
                  {hour % 3 === 0 ? hour : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WEEKDAY_SHORT.map((label, weekday) => (
              <tr key={label}>
                <td className="pr-2 text-right text-[10px]" style={{ color: "var(--page-text-muted)" }}>
                  {label}
                </td>
                {HOURS.map((hour) => {
                  const cell = grid.get(`${weekday}-${hour}`);
                  const alpha = cell ? intensity(cell, best) : null;
                  return (
                    <td key={hour}>
                      <div
                        title={
                          cell?.observed
                            ? `${label} ${hour}:00 — ${cell.posts} posts, ${cell.score} avg interactions`
                            : `${label} ${hour}:00 — no posts here`
                        }
                        className="h-4 w-full rounded-[3px]"
                        style={{
                          // A blank cell for "never tried", never a dark one:
                          // dark would read as "tried and failed".
                          backgroundColor:
                            alpha === null
                              ? "var(--sidebar-hover-bg)"
                              : `rgba(109,94,246,${alpha})`,
                        }}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {measured && (
        <p className="mt-3 text-[11px]" style={{ color: "var(--page-text-muted)" }}>
          {data.explanation} Empty cells are slots you have not posted in — not
          slots that performed badly.
        </p>
      )}
    </GlassCard>
  );
}

export default BestTimesHeatmap;
