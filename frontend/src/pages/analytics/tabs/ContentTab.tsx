import { ArrowDown, ArrowUp, FileText } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GlassCard } from "@/components/ui/GlassCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/utils";
import { metric, percent, type PostRow } from "@/lib/analytics";
import { chartAxis, chartTooltip, SERIES } from "../chart";

export type PostSort = "engagement" | "impressions" | "reach" | "date";
export type SortOrder = "asc" | "desc";

const COLUMNS: { key: PostSort | null; field: keyof PostRow; label: string }[] = [
  { key: "engagement", field: "engagement", label: "Engagement" },
  { key: "reach", field: "reach", label: "Reach" },
  { key: "impressions", field: "impressions", label: "Impressions" },
  { key: null, field: "clicks", label: "Clicks" },
  { key: null, field: "video_views", label: "Video views" },
];

/**
 * Content performance.
 *
 * Sorting is done by the server, not in the browser: the table shows at most
 * `limit` rows, so sorting the fetched page client-side would reorder a slice
 * rather than find the actual top posts.
 */
export function ContentTab({
  rows,
  loading,
  sort,
  order,
  onSortChange,
}: {
  rows: PostRow[];
  loading: boolean;
  sort: PostSort;
  order: SortOrder;
  onSortChange: (sort: PostSort, order: SortOrder) => void;
}) {
  const chartData = rows.slice(0, 10).map((r) => ({
    name: r.title.length > 24 ? `${r.title.slice(0, 24)}…` : r.title,
    engagement: r.engagement,
    reach: r.reach,
  }));

  function toggle(key: PostSort) {
    if (sort === key) onSortChange(key, order === "desc" ? "asc" : "desc");
    else onSortChange(key, "desc");
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton variant="card" height="280px" />
        <Skeleton variant="card" height="320px" />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <GlassCard>
        <EmptyState
          icon={<FileText className="h-7 w-7" />}
          title="No published posts in this window"
          description="Post performance appears once a post has been published and its metrics have been fetched."
        />
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <GlassCard>
        <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
          Top 10 by {sort === "date" ? "recency" : sort}
        </h3>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" horizontal={false} />
              <XAxis type="number" {...chartAxis} />
              <YAxis type="category" dataKey="name" width={150} {...chartAxis} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="engagement" name="Engagement" fill={SERIES.purple} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr style={{ color: "var(--page-text-muted)" }}>
                <th className="px-3 py-2 text-left font-medium">Post</th>
                <th className="px-3 py-2 text-left font-medium">
                  <SortHeader
                    label="Published"
                    active={sort === "date"}
                    order={order}
                    onClick={() => toggle("date")}
                  />
                </th>
                {COLUMNS.map((c) => (
                  <th key={c.field} className="px-3 py-2 text-right font-medium">
                    {c.key ? (
                      <SortHeader
                        label={c.label}
                        active={sort === c.key}
                        order={order}
                        onClick={() => toggle(c.key as PostSort)}
                        align="right"
                      />
                    ) : (
                      c.label
                    )}
                  </th>
                ))}
                <th className="px-3 py-2 text-right font-medium">Eng. rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={{ borderTop: "1px solid var(--surface-border)" }}>
                  <td
                    className="max-w-[280px] truncate px-3 py-3"
                    style={{ color: "var(--page-text)" }}
                    title={row.title}
                  >
                    {row.title}
                  </td>
                  <td
                    className="whitespace-nowrap px-3 py-3"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    {row.published_at ? row.published_at.slice(0, 10) : "—"}
                  </td>
                  {COLUMNS.map((c) => (
                    <td
                      key={c.field}
                      className="px-3 py-3 text-right tabular-nums"
                      style={{ color: "var(--page-text)" }}
                    >
                      {metric(row[c.field] as number)}
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

function SortHeader({
  label,
  active,
  order,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  order: SortOrder;
  onClick: () => void;
  align?: "left" | "right";
}) {
  const Icon = order === "desc" ? ArrowDown : ArrowUp;
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 transition-colors hover:text-purple-400",
        align === "right" && "justify-end"
      )}
      style={{ color: active ? "var(--page-heading)" : undefined }}
    >
      {label}
      {active && <Icon className="h-3 w-3" />}
    </button>
  );
}

export default ContentTab;
