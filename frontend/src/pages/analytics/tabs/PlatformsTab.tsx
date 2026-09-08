import { useMemo } from "react";
import { Layers } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GlassCard } from "@/components/ui/GlassCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { metric, percent, type PlatformRow } from "@/lib/analytics";
import { chartAxis, chartTooltip, platformColor, SERIES } from "../chart";

const COLUMNS: { key: keyof PlatformRow; label: string }[] = [
  { key: "followers", label: "Followers" },
  { key: "reach", label: "Reach" },
  { key: "impressions", label: "Impressions" },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
  { key: "shares", label: "Shares" },
  { key: "clicks", label: "Clicks" },
];

export function PlatformsTab({
  rows,
  loading,
}: {
  rows: PlatformRow[];
  loading: boolean;
}) {
  // Reach share only means something among platforms that report reach. Adding
  // a zero slice for the ones that don't would shrink everyone else's wedge.
  const reachShare = useMemo(
    () =>
      rows
        .filter((r) => r.reach !== null && r.reach > 0)
        .map((r) => ({ name: r.platform_name, value: r.reach as number, slug: r.platform })),
    [rows]
  );

  const engagementByPlatform = useMemo(
    () =>
      rows.map((r) => ({
        name: r.platform_name,
        slug: r.platform,
        interactions:
          (r.likes ?? 0) + (r.comments ?? 0) + (r.shares ?? 0) + (r.saves ?? 0),
      })),
    [rows]
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton variant="card" height="300px" />
          <Skeleton variant="card" height="300px" />
        </div>
        <Skeleton variant="card" height="240px" />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <GlassCard>
        <EmptyState
          icon={<Layers className="h-7 w-7" />}
          title="No platform data in this window"
          description="Connect a social account and the nightly sync will start recording per-platform metrics."
        />
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GlassCard>
          <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Interactions by platform
          </h3>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={engagementByPlatform}
                margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                <XAxis dataKey="name" {...chartAxis} />
                <YAxis {...chartAxis} />
                <Tooltip {...chartTooltip} />
                <Bar dataKey="interactions" name="Interactions" radius={[4, 4, 0, 0]}>
                  {engagementByPlatform.map((row, i) => (
                    <Cell key={row.slug} fill={platformColor(row.slug, i)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="mb-1 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Share of reach
          </h3>
          <p className="mb-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
            Only platforms that report reach appear here.
          </p>
          <div className="h-[240px]">
            {reachShare.length === 0 ? (
              <div
                className="flex h-full items-center justify-center text-sm"
                style={{ color: "var(--page-text-muted)" }}
              >
                None of your connected platforms report reach.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={reachShare}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                  >
                    {reachShare.map((row, i) => (
                      <Cell key={row.slug} fill={platformColor(row.slug, i)} />
                    ))}
                  </Pie>
                  <Tooltip {...chartTooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </GlassCard>
      </div>

      <GlassCard>
        <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
          Breakdown
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr style={{ color: "var(--page-text-muted)" }}>
                <th className="px-3 py-2 text-left font-medium">Platform</th>
                <th className="px-3 py-2 text-right font-medium">Accounts</th>
                {COLUMNS.map((c) => (
                  <th key={String(c.key)} className="px-3 py-2 text-right font-medium">
                    {c.label}
                  </th>
                ))}
                <th className="px-3 py-2 text-right font-medium">Eng. rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.platform} style={{ borderTop: "1px solid var(--surface-border)" }}>
                  <td className="px-3 py-3">
                    <span className="flex items-center gap-2" style={{ color: "var(--page-text)" }}>
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: platformColor(row.platform, i) }}
                      />
                      {row.platform_name}
                    </span>
                  </td>
                  <td
                    className="px-3 py-3 text-right tabular-nums"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    {row.accounts}
                  </td>
                  {COLUMNS.map((c) => (
                    <td
                      key={String(c.key)}
                      className="px-3 py-3 text-right tabular-nums"
                      style={{ color: "var(--page-text)" }}
                    >
                      {metric(row[c.key] as number | null)}
                    </td>
                  ))}
                  <td
                    className="px-3 py-3 text-right tabular-nums font-semibold"
                    style={{ color: SERIES.emerald }}
                  >
                    {percent(row.engagement_rate, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}

export default PlatformsTab;
