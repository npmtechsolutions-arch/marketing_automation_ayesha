/**
 * Revenue.
 *
 * Every figure is computed from the plans table and the subscription event
 * log. The page it replaces charted twelve months of invented revenue split
 * across invented plan names.
 *
 * Two honesty rules are visible in the UI:
 *
 *  * MRR counts only ACTIVE subscriptions. Past-due is shown beside it as
 *    at-risk rather than folded in, because an uncollected invoice is not
 *    income.
 *  * The trend can only be drawn from when the event log starts. Before that
 *    there is no history, so the chart says so instead of drawing zero and
 *    implying the business had none.
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  DollarSign,
  Info,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { showError } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import {
  adminApi,
  money,
  rate,
  type RevenueSummary,
  type RevenueTrend,
} from "@/lib/admin";
import { chartAxis, chartTooltip, SERIES } from "../analytics/chart";

const PLAN_COLORS = [SERIES.purple, SERIES.blue, SERIES.emerald, SERIES.amber, SERIES.cyan];

export default function AdminRevenuePage() {
  const [summary, setSummary] = useState<RevenueSummary | null>(null);
  const [trend, setTrend] = useState<RevenueTrend | null>(null);
  const [days, setDays] = useState(90);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t] = await Promise.all([
        adminApi.revenue(30),
        adminApi.revenueTrend(days),
      ]);
      setSummary(s);
      setTrend(t);
    } catch {
      showError("Could not load revenue metrics.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const planMix = (summary?.by_plan ?? []).filter((row) => row.organizations > 0);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Revenue
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Computed from active subscriptions and current plan prices.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {[30, 90, 365].map((option) => (
              <button
                key={option}
                onClick={() => setDays(option)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs transition-colors",
                  days === option && "bg-purple-500/20 text-purple-300"
                )}
                style={
                  days === option
                    ? undefined
                    : { color: "var(--page-text-secondary)" }
                }
              >
                {option}d
              </button>
            ))}
            <button
              onClick={load}
              disabled={loading}
              className="rounded-xl p-2 disabled:opacity-50"
              style={{
                backgroundColor: "var(--sidebar-hover-bg)",
                color: "var(--page-text-secondary)",
              }}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </button>
          </div>
        </div>

        {loading && !summary ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <StatCard key={i} label="" value="" loading />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="MRR"
              value={money(summary?.mrr)}
              icon={<DollarSign className="h-5 w-5" />}
            />
            <StatCard
              label="ARR"
              value={money(summary?.arr)}
              changeLabel="MRR × 12"
              icon={<TrendingUp className="h-5 w-5" />}
            />
            <StatCard
              label="At risk (past due)"
              value={money(summary?.at_risk_mrr)}
              icon={<AlertTriangle className="h-5 w-5" />}
            />
            <StatCard
              label="Paying organizations"
              value={String(summary?.paying_organizations ?? 0)}
              icon={<UserCheck className="h-5 w-5" />}
            />
          </div>
        )}

        {(summary?.unpriced_active_organizations ?? 0) > 0 && (
          <div
            className="flex items-start gap-3 rounded-xl px-4 py-3 text-sm"
            style={{
              backgroundColor: "rgba(245,158,11,0.10)",
              border: "1px solid rgba(245,158,11,0.28)",
              color: "var(--page-text)",
            }}
          >
            <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: SERIES.amber }} />
            <span>
              MRR excludes {summary?.unpriced_active_organizations} active{" "}
              {summary?.unpriced_tiers.join(", ")} organization
              {summary?.unpriced_active_organizations === 1 ? "" : "s"}, which are
              priced by negotiation and carry no amount in the plans table. The real
              figure is higher than the one above.
            </span>
          </div>
        )}

        <GlassCard>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              MRR trend
            </h3>
            <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              {trend?.has_history
                ? `Reconstructed from subscription events since ${trend.tracking_since?.slice(0, 10)}`
                : "No subscription history recorded yet"}
            </p>
          </div>

          {loading && !trend ? (
            <Skeleton variant="card" height="300px" />
          ) : !trend?.has_history ? (
            <div
              className="flex h-[280px] flex-col items-center justify-center gap-2 text-center text-sm"
              style={{ color: "var(--page-text-muted)" }}
            >
              <TrendingDown className="h-8 w-8 opacity-40" />
              <p className="max-w-md">
                Subscription changes are recorded from the moment this shipped, so
                there is no history to chart yet. The line will fill in as
                organizations sign up, upgrade and cancel.
              </p>
            </div>
          ) : (
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend.series} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="mrrFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={SERIES.emerald} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={SERIES.emerald} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                  <XAxis dataKey="date" {...chartAxis} minTickGap={40} />
                  <YAxis {...chartAxis} />
                  <Tooltip {...chartTooltip} />
                  <Area
                    type="stepAfter"
                    dataKey="mrr"
                    name="MRR"
                    stroke={SERIES.emerald}
                    strokeWidth={2}
                    fill="url(#mrrFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <GlassCard>
            <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              Revenue by plan
            </h3>
            {planMix.length === 0 ? (
              <p className="py-8 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
                No organizations yet.
              </p>
            ) : (
              <>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={planMix} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                      <XAxis dataKey="plan" {...chartAxis} />
                      <YAxis {...chartAxis} />
                      <Tooltip {...chartTooltip} />
                      <Bar dataKey="mrr" name="MRR" radius={[4, 4, 0, 0]}>
                        {planMix.map((row, i) => (
                          <Cell key={row.plan} fill={PLAN_COLORS[i % PLAN_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <table className="mt-4 w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--page-text-muted)" }}>
                      <th className="px-2 py-1.5 text-left font-medium">Plan</th>
                      <th className="px-2 py-1.5 text-right font-medium">Orgs</th>
                      <th className="px-2 py-1.5 text-right font-medium">Paying</th>
                      <th className="px-2 py-1.5 text-right font-medium">MRR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {planMix.map((row) => (
                      <tr key={row.plan} style={{ borderTop: "1px solid var(--surface-border)" }}>
                        <td className="px-2 py-2 capitalize" style={{ color: "var(--page-text)" }}>
                          {row.plan}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                          {row.organizations}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                          {row.active}
                        </td>
                        <td className="px-2 py-2 text-right font-semibold tabular-nums" style={{ color: "var(--page-heading)" }}>
                          {money(row.mrr)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </GlassCard>

          <div className="space-y-6">
            <GlassCard>
              <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
                Churn — last {summary?.churn.days ?? 30} days
              </h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                <Metric label="Cancelled" value={String(summary?.churn.churned_organizations ?? 0)} />
                <Metric label="Lost MRR" value={money(summary?.churn.lost_mrr)} />
                <Metric label="Rate" value={rate(summary?.churn.churn_rate)} />
              </div>
              {summary?.churn.churn_rate === null && (
                <p className="mt-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
                  No rate: there were no paying organizations that could have churned.
                </p>
              )}
            </GlassCard>

            <GlassCard>
              <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
                Trials — last {summary?.trials.days ?? 30} days
              </h3>
              <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
                <Metric label="In trial" value={String(summary?.trials.trialing_now ?? 0)} />
                <Metric label="Ended" value={String(summary?.trials.trials_ended ?? 0)} />
                <Metric label="Converted" value={String(summary?.trials.converted ?? 0)} />
                <Metric label="Rate" value={rate(summary?.trials.conversion_rate)} />
              </div>
              {summary?.trials.conversion_rate === null && (
                <p className="mt-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
                  No rate: no trial ended in this window.
                </p>
              )}
            </GlassCard>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl px-2 py-3"
      style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
    >
      <p className="text-lg font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>
        {value}
      </p>
      <p className="mt-0.5 text-[11px]" style={{ color: "var(--page-text-muted)" }}>
        {label}
      </p>
    </motion.div>
  );
}
