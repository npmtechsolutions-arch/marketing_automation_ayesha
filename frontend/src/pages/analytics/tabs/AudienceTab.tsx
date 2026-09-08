import { Users } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { metric, percent, signed, type AudiencePayload } from "@/lib/analytics";
import { chartAxis, chartTooltip, SERIES } from "../chart";

export function AudienceTab({
  data,
  loading,
}: {
  data: AudiencePayload | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <StatCard key={i} label="" value="" loading />
          ))}
        </div>
        <Skeleton variant="card" height="340px" />
      </div>
    );
  }

  const series = data?.series ?? [];

  if (series.length === 0) {
    return (
      <GlassCard>
        <EmptyState
          icon={<Users className="h-7 w-7" />}
          title="No follower history yet"
          description="Follower counts are recorded by the nightly sync. A newly connected account has its first data point the following day."
        />
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Followers"
          value={metric(data?.current)}
          change={data?.change_percent ?? undefined}
          changeLabel="over this window"
          icon={<Users className="h-5 w-5" />}
        />
        <StatCard label="Net change" value={signed(data?.change)} />
        <StatCard label="Growth" value={percent(data?.change_percent, 2)} />
      </div>

      <GlassCard>
        <div className="mb-4">
          <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Follower growth
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
            One point per day, summed across every connected account. Growth is the last
            value minus the first — never a sum of daily snapshots.
          </p>
        </div>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="followersFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SERIES.purple} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={SERIES.purple} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
              <XAxis dataKey="date" {...chartAxis} />
              {/* Followers rarely start near zero, so a zero-based axis would
                  flatten every real movement into a straight line. */}
              <YAxis domain={["auto", "auto"]} {...chartAxis} />
              <Tooltip {...chartTooltip} />
              <Area
                type="monotone"
                dataKey="followers"
                name="Followers"
                stroke={SERIES.purple}
                strokeWidth={2}
                fill="url(#followersFill)"
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>
    </div>
  );
}

export default AudienceTab;
