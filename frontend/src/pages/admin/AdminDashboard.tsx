/**
 * The admin overview.
 *
 * Every figure comes from an endpoint. The previous version of this page was
 * entirely hard-coded: invented user counts with invented month-over-month
 * percentages, twelve months of invented revenue, and a "recent signups" table
 * of invented people with invented email addresses. That last one is the worst
 * of the three -- it is indistinguishable from real customer data, so there is
 * no way for an operator to tell they are looking at a mock.
 *
 * Where a number genuinely is not known yet -- month-over-month deltas, which
 * need history the subscription log has only just started collecting -- this
 * page shows no delta rather than a plausible one.
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  CreditCard,
  DollarSign,
  FileText,
  RefreshCw,
  Shield,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { showError } from "@/components/ui/Toast";
import { cn, formatNumber } from "@/lib/utils";
import {
  adminApi,
  money,
  rate,
  type ApiErrorSummary,
  type ConnectionHealth,
  type RevenueSummary,
  type RevenueTrend,
} from "@/lib/admin";
import { chartAxis, chartTooltip, SERIES } from "../analytics/chart";

interface PlatformStats {
  total_users: number;
  active_users: number;
  suspended_users: number;
  total_accounts: number;
  total_posts: number;
  published_posts: number;
  total_revenue_estimate: number;
  accounts_by_tier: Record<string, number>;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [trend, setTrend] = useState<RevenueTrend | null>(null);
  const [health, setHealth] = useState<ConnectionHealth | null>(null);
  const [errors, setErrors] = useState<ApiErrorSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    // Settled rather than all: one failing panel should not blank the page.
    const [s, r, t, h, e] = await Promise.allSettled([
      adminApi.stats(),
      adminApi.revenue(30),
      adminApi.revenueTrend(90),
      adminApi.connectionHealth(),
      adminApi.errorSummary(7),
    ]);
    if (s.status === "fulfilled") setStats(s.value as PlatformStats);
    if (r.status === "fulfilled") setRevenue(r.value);
    if (t.status === "fulfilled") setTrend(t.value);
    if (h.status === "fulfilled") setHealth(h.value);
    if (e.status === "fulfilled") setErrors(e.value);
    if ([s, r, t, h, e].every((result) => result.status === "rejected")) {
      showError("Could not load the admin overview.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const failed = health?.counts?.failed ?? 0;
  const recentErrors = errors?.total ?? 0;

  return (
    <DashboardLayout>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-600/20 to-orange-600/20">
              <Shield className="h-6 w-6 text-red-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--page-heading)" }}>
                Admin Panel
              </h1>
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                Platform overview
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {failed === 0 && recentErrors === 0 ? (
              <Badge variant="success" dot>All clear</Badge>
            ) : (
              <Badge variant="warning" dot>
                {failed} failed connection{failed === 1 ? "" : "s"} · {recentErrors} error
                {recentErrors === 1 ? "" : "s"} this week
              </Badge>
            )}
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

        {/* No `change` props anywhere here: month-over-month needs history the
            subscription log only started collecting, and an invented delta is
            what this page is being fixed for. */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard
            label="Users"
            value={formatNumber(stats?.total_users ?? 0)}
            icon={<Users className="h-5 w-5" />}
            loading={loading && !stats}
          />
          <StatCard
            label="Workspaces"
            value={formatNumber(stats?.total_accounts ?? 0)}
            icon={<Building2 className="h-5 w-5" />}
            loading={loading && !stats}
          />
          <StatCard
            label="Paying orgs"
            value={formatNumber(revenue?.paying_organizations ?? 0)}
            icon={<CreditCard className="h-5 w-5" />}
            loading={loading && !revenue}
          />
          <StatCard
            label="MRR"
            value={money(revenue?.mrr)}
            icon={<DollarSign className="h-5 w-5" />}
            loading={loading && !revenue}
          />
          <StatCard
            label="Posts published"
            value={formatNumber(stats?.published_posts ?? 0)}
            icon={<FileText className="h-5 w-5" />}
            loading={loading && !stats}
          />
          <StatCard
            label="Churn (30d)"
            value={rate(revenue?.churn.churn_rate)}
            icon={<AlertTriangle className="h-5 w-5" />}
            loading={loading && !revenue}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <GlassCard className="lg:col-span-2">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
                  MRR
                </h3>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                  {trend?.has_history
                    ? `Since ${trend.tracking_since?.slice(0, 10)}`
                    : "No subscription history recorded yet"}
                </p>
              </div>
              <Link
                to="/admin/revenue"
                className="flex items-center gap-1 text-xs"
                style={{ color: "var(--accent-purple)" }}
              >
                Revenue detail <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="h-64">
              {!trend?.has_history ? (
                <div
                  className="flex h-full items-center justify-center px-6 text-center text-sm"
                  style={{ color: "var(--page-text-muted)" }}
                >
                  Subscription changes are recorded from now on. The line fills in as
                  organizations sign up, upgrade and cancel.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend.series} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                    <defs>
                      <linearGradient id="adminMrr" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={SERIES.emerald} stopOpacity={0.3} />
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
                      fill="url(#adminMrr)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </GlassCard>

          <div className="space-y-6">
            <GlassCard>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
                  Connections
                </h3>
                <Link to="/admin/health" className="text-xs" style={{ color: "var(--accent-purple)" }}>
                  Detail
                </Link>
              </div>
              <ul className="space-y-2 text-sm">
                {["connected", "expiring", "failed", "unknown"].map((state) => (
                  <li key={state} className="flex items-center justify-between">
                    <span className="capitalize" style={{ color: "var(--page-text-secondary)" }}>
                      {state}
                    </span>
                    <span
                      className="font-semibold tabular-nums"
                      style={{
                        color:
                          state === "failed" && (health?.counts?.[state] ?? 0) > 0
                            ? SERIES.rose
                            : "var(--page-heading)",
                      }}
                    >
                      {health?.counts?.[state] ?? 0}
                    </span>
                  </li>
                ))}
              </ul>
            </GlassCard>

            <GlassCard>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
                  Errors — 7 days
                </h3>
                <Link to="/admin/errors" className="text-xs" style={{ color: "var(--accent-purple)" }}>
                  Detail
                </Link>
              </div>
              {recentErrors === 0 ? (
                <p
                  className="flex items-center gap-2 py-2 text-sm"
                  style={{ color: "var(--page-text-secondary)" }}
                >
                  <CheckCircle2 className="h-4 w-4" style={{ color: SERIES.emerald }} />
                  Nothing unhandled.
                </p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {errors?.by_exception.slice(0, 5).map((row) => (
                    <li key={row.exception_class} className="flex items-center gap-2">
                      <AlertOctagon className="h-3.5 w-3.5 shrink-0" style={{ color: SERIES.rose }} />
                      <span className="truncate font-mono text-xs" style={{ color: "var(--page-text)" }}>
                        {row.exception_class.split(".").pop()}
                      </span>
                      <span className="ml-auto tabular-nums" style={{ color: "var(--page-text-muted)" }}>
                        {row.count}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </GlassCard>
          </div>
        </div>

        <GlassCard>
          <h3 className="mb-4 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Organizations by plan
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr style={{ color: "var(--page-text-muted)" }}>
                  <th className="px-3 py-2 text-left font-medium">Plan</th>
                  <th className="px-3 py-2 text-right font-medium">Organizations</th>
                  <th className="px-3 py-2 text-right font-medium">Paying</th>
                  <th className="px-3 py-2 text-right font-medium">MRR</th>
                </tr>
              </thead>
              <tbody>
                {(revenue?.by_plan ?? []).map((row) => (
                  <tr key={row.plan} style={{ borderTop: "1px solid var(--surface-border)" }}>
                    <td className="px-3 py-2.5 capitalize" style={{ color: "var(--page-text)" }}>
                      {row.plan}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                      {row.organizations}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                      {row.active}
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold tabular-nums" style={{ color: "var(--page-heading)" }}>
                      {money(row.mrr)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </motion.div>
    </DashboardLayout>
  );
}
