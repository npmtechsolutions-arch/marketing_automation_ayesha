import { useMemo } from "react";
import { Eye, Heart, TrendingUp, Users } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { METRIC_LABELS, metric, percent, signed, type OverviewPayload } from "@/lib/analytics";
import { chartAxis, chartTooltip, SERIES } from "../chart";

const HEADLINE: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "followers", label: "Followers", icon: <Users className="h-5 w-5" /> },
  { key: "reach", label: "Reach", icon: <Eye className="h-5 w-5" /> },
  { key: "impressions", label: "Impressions", icon: <TrendingUp className="h-5 w-5" /> },
  { key: "engagement_rate", label: "Engagement rate", icon: <Heart className="h-5 w-5" /> },
];

/** Metrics worth charting side by side against the previous window. */
const COMPARABLE = ["likes", "comments", "shares", "saves", "clicks", "profile_visits"];

export function OverviewTab({
  data,
  loading,
}: {
  data: OverviewPayload | null;
  loading: boolean;
}) {
  // Only metrics somebody actually reports. A bar pair of two zeroes for a
  // metric no connected platform measures is noise pretending to be a finding.
  const comparison = useMemo(() => {
    if (!data) return [];
    return COMPARABLE.filter(
      (key) => data.metrics[key]?.value !== null || data.metrics[key]?.previous !== null
    ).map((key) => ({
      name: METRIC_LABELS[key] ?? key,
      current: data.metrics[key]?.value ?? 0,
      previous: data.metrics[key]?.previous ?? 0,
    }));
  }, [data]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <StatCard key={i} label="" value="" loading />
          ))}
        </div>
        <Skeleton variant="card" height="320px" />
      </div>
    );
  }

  if (!data || !data.has_data) {
    return (
      <GlassCard>
        <EmptyState
          icon={<TrendingUp className="h-7 w-7" />}
          title="No analytics for this window"
          description="Metrics arrive from the nightly sync once an account has been connected for a full day. Pick a wider range, or check back tomorrow."
        />
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {HEADLINE.map((item) => {
          const m = data.metrics[item.key];
          return (
            <StatCard
              key={item.key}
              label={item.label}
              value={
                item.key === "engagement_rate" ? percent(m?.value) : metric(m?.value)
              }
              // Undefined, not zero: StatCard hides the trend chip entirely when
              // there is no comparable previous period, rather than drawing a
              // flat 0% that reads as "no change".
              change={m?.change_percent ?? undefined}
              changeLabel="vs previous period"
              icon={item.icon}
            />
          );
        })}
      </div>

      {comparison.length > 0 && (
        <GlassCard>
          <div className="mb-4">
            <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              This period vs last
            </h3>
            <p className="mt-0.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
              {data.range.days} days to {data.range.end.slice(0, 10)} ({data.range.timezone})
              , compared with the {data.range.days} days before it
            </p>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparison} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                <XAxis dataKey="name" {...chartAxis} />
                <YAxis {...chartAxis} />
                <Tooltip {...chartTooltip} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="previous" name="Previous" fill={SERIES.muted} radius={[4, 4, 0, 0]} />
                <Bar dataKey="current" name="Current" fill={SERIES.purple} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      )}

      <GlassCard>
        <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
          All metrics
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr style={{ color: "var(--page-text-muted)" }}>
                <th className="px-3 py-2 text-left font-medium">Metric</th>
                <th className="px-3 py-2 text-right font-medium">Value</th>
                <th className="px-3 py-2 text-right font-medium">Previous</th>
                <th className="px-3 py-2 text-right font-medium">Change</th>
                <th className="px-3 py-2 text-right font-medium">%</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.metrics).map(([key, m]) => (
                <tr key={key} style={{ borderTop: "1px solid var(--surface-border)" }}>
                  <td className="px-3 py-2.5" style={{ color: "var(--page-text)" }}>
                    {METRIC_LABELS[key] ?? key}
                  </td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums font-semibold"
                    style={{ color: "var(--page-heading)" }}
                  >
                    {key === "engagement_rate" ? percent(m.value) : metric(m.value)}
                  </td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    {key === "engagement_rate" ? percent(m.previous) : metric(m.previous)}
                  </td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums"
                    style={{
                      color:
                        m.change === null
                          ? "var(--page-text-muted)"
                          : m.change >= 0
                            ? SERIES.emerald
                            : SERIES.rose,
                    }}
                  >
                    {signed(m.change)}
                  </td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    {m.change_percent === null ? "—" : percent(m.change_percent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
          A dash means the platform does not report that metric — not that it is zero.
        </p>
      </GlassCard>
    </div>
  );
}

export default OverviewTab;
