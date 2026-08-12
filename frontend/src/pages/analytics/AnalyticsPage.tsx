import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Eye,
  Heart,
  TrendingUp,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Sparkles,
  Clock,
  Zap,
  BarChart3,
  RefreshCw,
  Lightbulb,
  Trophy,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import { Instagram, Linkedin, Twitter, Facebook, Youtube } from "@/components/shared/SocialIcons";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, formatNumber, formatDate } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import api, { getAccountId } from "@/lib/api";

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as const } },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type DateRange = "7d" | "30d" | "90d";
type TrendMetric = "reach" | "engagement" | "impressions";
type SortField = "reach" | "engagement_rate" | "published_at";
type SortDirection = "asc" | "desc";

const platformIconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter,
  facebook: Facebook,
  youtube: Youtube,
};

const platformColors: Record<string, string> = {
  instagram: "#E4405F",
  linkedin: "#0A66C2",
  twitter: "#1DA1F2",
  facebook: "#1877F2",
  youtube: "#FF0000",
  tiktok: "#010101",
};

// Refined series palette — matches the Dashboard chart theme.
const SERIES = {
  violet: "#7c3aed",
  sky: "#38bdf8",
  emerald: "#10b981",
  amber: "#f59e0b",
} as const;

// ---------------------------------------------------------------------------
// Heatmap helpers
// ---------------------------------------------------------------------------
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);
const HEAT_SCALE = [
  "bg-purple-500/[0.06]",
  "bg-purple-500/[0.16]",
  "bg-purple-500/30",
  "bg-purple-500/50",
  "bg-purple-500/70",
  "bg-purple-500/90",
];
function getHeatColor(value: number): string {
  if (value <= 15) return HEAT_SCALE[0];
  if (value <= 30) return HEAT_SCALE[1];
  if (value <= 50) return HEAT_SCALE[2];
  if (value <= 70) return HEAT_SCALE[3];
  if (value <= 85) return HEAT_SCALE[4];
  return HEAT_SCALE[5];
}

// ---------------------------------------------------------------------------
// Section header — tinted icon chip, matches Dashboard
// ---------------------------------------------------------------------------
function SectionHeader({
  icon: Icon,
  accent,
  title,
  subtitle,
  action,
}: {
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div className="flex items-center gap-3">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${accent}1f`, border: `1px solid ${accent}38`, color: accent }}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-bold sm:text-lg" style={{ color: "var(--page-heading)" }}>
            {title}
          </h2>
          {subtitle && (
            <p className="mt-0.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics Page
// ---------------------------------------------------------------------------
export default function AnalyticsPage() {
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === "dark";

  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [activeMetric, setActiveMetric] = useState<TrendMetric>("reach");
  const [sortField, setSortField] = useState<SortField>("engagement_rate");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  // API data
  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [topPosts, setTopPosts] = useState<any[]>([]);
  const [platformBreakdown, setPlatformBreakdown] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (range: DateRange, showRefreshing = false) => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) {
      setLoading(false);
      setRefreshing(false);
      return;
    }
    try {
      showRefreshing ? setRefreshing(true) : setLoading(true);
      const [ovRes, trRes, tpRes, pbRes] = await Promise.allSettled([
        api.get(`/accounts/${activeAccountId}/analytics/overview?period=${range}`),
        api.get(`/accounts/${activeAccountId}/analytics/trends?period=${range}&group_by=day`),
        api.get(`/accounts/${activeAccountId}/analytics/top-posts?period=${range}&limit=10`),
        api.get(`/accounts/${activeAccountId}/analytics/platform-breakdown?period=${range}`),
      ]);
      if (ovRes.status === "fulfilled") setOverview((ovRes.value as any).data);
      if (trRes.status === "fulfilled") {
        const d = (trRes.value as any).data;
        setTrends(Array.isArray(d) ? d : []);
      }
      if (tpRes.status === "fulfilled") {
        const d = (tpRes.value as any).data;
        setTopPosts(Array.isArray(d) ? d : []);
      }
      if (pbRes.status === "fulfilled") {
        const d = (pbRes.value as any).data;
        setPlatformBreakdown(Array.isArray(d) ? d : []);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { loadData(dateRange); }, []);

  const handleRangeChange = (range: DateRange) => {
    setDateRange(range);
    loadData(range, true);
  };

  // Sorted top posts
  const sortedPosts = useMemo(() => {
    return [...topPosts].sort((a, b) => {
      let aVal: number, bVal: number;
      if (sortField === "published_at") {
        aVal = new Date(a.published_at || 0).getTime();
        bVal = new Date(b.published_at || 0).getTime();
      } else if (sortField === "reach") {
        aVal = a.total_engagement || 0;
        bVal = b.total_engagement || 0;
      } else {
        aVal = a.engagement_rate || 0;
        bVal = b.engagement_rate || 0;
      }
      return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });
  }, [topPosts, sortField, sortDir]);

  function handleSort(field: SortField) {
    if (sortField === field) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortField(field); setSortDir("desc"); }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3" style={{ color: "var(--page-text-muted)" }} />;
    return sortDir === "desc"
      ? <ArrowDown className="w-3 h-3" style={{ color: SERIES.violet }} />
      : <ArrowUp className="w-3 h-3" style={{ color: SERIES.violet }} />;
  }

  // Engagement breakdown from platform data
  const engagementBreakdown = useMemo(() => {
    const totals = { likes: 0, comments: 0, shares: 0, clicks: 0 };
    platformBreakdown.forEach((p) => {
      totals.likes += p.likes || 0;
      totals.comments += p.comments || 0;
      totals.shares += p.shares || 0;
      totals.clicks += p.clicks || 0;
    });
    return [
      { name: "Likes", value: totals.likes, color: SERIES.violet },
      { name: "Comments", value: totals.comments, color: SERIES.sky },
      { name: "Shares", value: totals.shares, color: SERIES.emerald },
      { name: "Clicks", value: totals.clicks, color: SERIES.amber },
    ].filter((e) => e.value > 0);
  }, [platformBreakdown]);

  const totalEngagement = engagementBreakdown.reduce((s, d) => s + d.value, 0);

  // Chart data
  const chartData = trends.map((t) => ({
    date: new Date(t.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    reach: t.reach || 0,
    engagement: t.engagement || 0,
    impressions: t.impressions || 0,
  }));

  const platformChartData = platformBreakdown.map((p) => ({
    name: p.platform.charAt(0).toUpperCase() + p.platform.slice(1),
    likes: p.likes || 0,
    comments: p.comments || 0,
    shares: p.shares || 0,
    color: platformColors[p.platform] || "#6366F1",
  }));

  // Static heatmap (engagement pattern estimation — real heatmap needs per-hour data)
  const heatmapData = useMemo(() => DAYS.map((day) =>
    HOURS.map((hour) => {
      let base = 10;
      if (hour >= 9 && hour <= 17) base += 40;
      if (hour >= 10 && hour <= 12) base += 25;
      if (day === "Tue" || day === "Thu") base += 20;
      if (day === "Sat" || day === "Sun") base -= 15;
      if (hour >= 0 && hour <= 5) base = 5;
      return Math.max(0, Math.min(100, base + Math.round(Math.random() * 20 - 10)));
    })
  ), []);

  // Theme-aware chart palette
  const chart = {
    grid: isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)",
    axis: isDark ? "#94a3b8" : "#64748b",
    axisStrong: isDark ? "#cbd5e1" : "#475569",
    tooltipBg: isDark ? "rgba(18,18,28,0.96)" : "rgba(255,255,255,0.98)",
    tooltipBorder: isDark ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.08)",
    tooltipText: isDark ? "#f8fafc" : "#0f172a",
    tooltipShadow: isDark ? "0 16px 36px rgba(0,0,0,0.6)" : "0 12px 32px rgba(16,24,40,0.12)",
    activeDotStroke: isDark ? "#0f172a" : "#ffffff",
  };

  // Shared themed tooltip (area + bar). Reads value color from series color/fill.
  function ChartTooltip({ active, payload, label }: any) {
    if (!active || !payload?.length) return null;
    return (
      <div
        style={{
          background: chart.tooltipBg,
          border: `1px solid ${chart.tooltipBorder}`,
          borderRadius: 14,
          padding: "10px 14px",
          color: chart.tooltipText,
          boxShadow: chart.tooltipShadow,
          backdropFilter: "blur(12px)",
        }}
      >
        {label != null && (
          <p className="mb-2 text-xs font-bold" style={{ color: chart.tooltipText }}>{label}</p>
        )}
        <div className="space-y-1">
          {payload.map((p: any) => (
            <div key={p.dataKey ?? p.name} className="flex items-center gap-2.5 text-xs font-medium" style={{ color: chart.tooltipText }}>
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color || p.fill }} />
              <span className="capitalize" style={{ opacity: 0.75 }}>{p.dataKey ?? p.name}:</span>
              <span className="ml-auto font-bold tabular-nums">{formatNumber(p.value)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  function PieTooltip({ active, payload }: any) {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    return (
      <div
        style={{
          background: chart.tooltipBg,
          border: `1px solid ${chart.tooltipBorder}`,
          borderRadius: 14,
          padding: "10px 14px",
          color: chart.tooltipText,
          boxShadow: chart.tooltipShadow,
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="flex items-center gap-2.5 text-xs font-medium">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: d.payload.color }} />
          <span style={{ opacity: 0.75 }}>{d.name}:</span>
          <span className="ml-auto font-bold tabular-nums">{formatNumber(d.value)}</span>
        </div>
      </div>
    );
  }

  const metricColors: Record<TrendMetric, { stroke: string; id: string }> = {
    reach: { stroke: SERIES.violet, id: "gradAnalyticsReach" },
    engagement: { stroke: SERIES.sky, id: "gradAnalyticsEng" },
    impressions: { stroke: SERIES.emerald, id: "gradAnalyticsImp" },
  };

  const metricTabs: { key: TrendMetric; label: string }[] = [
    { key: "reach", label: "Reach" },
    { key: "engagement", label: "Engagement" },
    { key: "impressions", label: "Impressions" },
  ];

  const dateRanges: { key: DateRange; label: string }[] = [
    { key: "7d", label: "7d" },
    { key: "30d", label: "30d" },
    { key: "90d", label: "90d" },
  ];

  const isEmpty = !loading && chartData.length === 0 && topPosts.length === 0;

  // Reusable segmented-control button styling
  const segItem = (active: boolean): React.CSSProperties =>
    active
      ? {
          background: "rgba(124,58,237,0.14)",
          border: "1px solid rgba(124,58,237,0.30)",
          color: "var(--page-heading)",
        }
      : { border: "1px solid transparent", color: "var(--page-text-muted)" };

  return (
    <DashboardLayout>
      <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6 pb-8">

        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl" style={{ color: "var(--page-heading)" }}>
              Analytics
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Track performance across all your platforms
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div
              className="flex items-center gap-1 rounded-xl p-1"
              style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
            >
              {dateRanges.map((dr) => (
                <button
                  key={dr.key}
                  onClick={() => handleRangeChange(dr.key)}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 cursor-pointer"
                  style={segItem(dateRange === dr.key)}
                >
                  {dr.label}
                </button>
              ))}
            </div>
            {refreshing && <RefreshCw className="w-4 h-4 animate-spin" style={{ color: SERIES.violet }} />}
          </div>
        </motion.div>

        {/* Stats Row */}
        <motion.div variants={staggerContainer} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loading ? (
            [...Array(4)].map((_, i) => <StatCard key={i} label="" value="" loading />)
          ) : (
            <>
              <motion.div variants={fadeUp}>
                <StatCard label="Total Reach" value={overview ? formatNumber(overview.total_reach) : "0"}
                  change={overview?.comparison?.reach_change_pct ?? null} changeLabel="vs last period"
                  icon={<Eye className="w-5 h-5" />} />
              </motion.div>
              <motion.div variants={fadeUp}>
                <StatCard label="Total Engagement" value={overview ? formatNumber(overview.total_engagement) : "0"}
                  change={overview?.comparison?.engagement_change_pct ?? null} changeLabel="vs last period"
                  icon={<Heart className="w-5 h-5" />} />
              </motion.div>
              <motion.div variants={fadeUp}>
                <StatCard label="Avg Engagement Rate"
                  value={overview ? `${(overview.avg_engagement_rate * 100).toFixed(2)}%` : "0%"}
                  change={overview?.comparison?.engagement_rate_change_pct ?? null} changeLabel="vs last period"
                  icon={<TrendingUp className="w-5 h-5" />} />
              </motion.div>
              <motion.div variants={fadeUp}>
                <StatCard label="Posts Analyzed" value={overview ? String(overview.total_posts) : "0"}
                  icon={<BarChart3 className="w-5 h-5" />} />
              </motion.div>
            </>
          )}
        </motion.div>

        {/* No data state */}
        {isEmpty && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <div className="text-center py-12">
                <BarChart3 className="w-12 h-12 mx-auto mb-4" style={{ color: "var(--page-text-muted)", opacity: 0.5 }} />
                <p className="mb-2 font-medium" style={{ color: "var(--page-text-secondary)" }}>No analytics data yet</p>
                <p className="text-sm" style={{ color: "var(--page-text-muted)" }}>
                  Publish posts and come back to see your performance metrics here.
                </p>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* Performance Trends Chart */}
        {!loading && chartData.length > 0 && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <SectionHeader
                icon={TrendingUp}
                accent={SERIES.violet}
                title="Performance Trends"
                subtitle="Track key metrics over time"
                action={
                  <div
                    className="flex items-center gap-1 rounded-xl p-1"
                    style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
                  >
                    {metricTabs.map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveMetric(tab.key)}
                        className="rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all duration-200 cursor-pointer"
                        style={segItem(activeMetric === tab.key)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                }
              />
              <div className="h-[360px] -mx-2" role="img" aria-label={`${activeMetric} performance trend over the selected period`}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <AreaChart data={chartData}>
                    <defs>
                      {Object.entries(metricColors).map(([_key, val]) => (
                        <linearGradient key={val.id} id={val.id} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={val.stroke} stopOpacity={0.35} />
                          <stop offset="100%" stopColor={val.stroke} stopOpacity={0} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: chart.axis, fontSize: 11 }} dy={8} interval="preserveStartEnd" />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: chart.axis, fontSize: 11 }} tickFormatter={(v) => formatNumber(v)} dx={-8} width={50} />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: chart.grid, strokeWidth: 1.5 }} />
                    <Area type="monotone" dataKey={activeMetric} stroke={metricColors[activeMetric].stroke} strokeWidth={2.5}
                      fill={`url(#${metricColors[activeMetric].id})`} dot={false}
                      activeDot={{ r: 5, fill: metricColors[activeMetric].stroke, stroke: chart.activeDotStroke, strokeWidth: 2 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* Platform Comparison */}
        {!loading && platformChartData.length > 0 && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <SectionHeader
                icon={BarChart3}
                accent={SERIES.sky}
                title="Platform Comparison"
                subtitle="Engagement breakdown by platform"
              />
              <div className="mb-4 flex items-center gap-6">
                {[
                  { label: "Likes", color: SERIES.violet },
                  { label: "Comments", color: SERIES.sky },
                  { label: "Shares", color: SERIES.emerald },
                ].map((l) => (
                  <div key={l.label} className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full" style={{ background: l.color }} />
                    <span className="text-xs" style={{ color: "var(--page-text-secondary)" }}>{l.label}</span>
                  </div>
                ))}
              </div>
              <div className="h-[280px] -mx-2">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <BarChart data={platformChartData} layout="vertical" barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} horizontal={false} />
                    <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: chart.axis, fontSize: 11 }} tickFormatter={(v) => formatNumber(v)} />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: chart.axisStrong, fontSize: 12 }} width={80} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: chart.grid }} />
                    <Bar dataKey="likes" stackId="a" fill={SERIES.violet} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="comments" stackId="a" fill={SERIES.sky} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="shares" stackId="a" fill={SERIES.emerald} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* Content Performance Table */}
        {!loading && sortedPosts.length > 0 && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <SectionHeader
                icon={Trophy}
                accent={SERIES.emerald}
                title="Content Performance"
                subtitle="Click column headers to sort"
              />
              <div className="overflow-x-auto -mx-5">
                <table className="w-full min-w-[700px]">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                      <th className="text-left px-5 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Content</th>
                      <th className="text-left px-3 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Platform</th>
                      <th className="text-left px-3 py-3 text-xs font-medium uppercase tracking-wider cursor-pointer" style={{ color: "var(--page-text-muted)" }}
                        onClick={() => handleSort("published_at")}>
                        <span className="flex items-center gap-1">Date <SortIcon field="published_at" /></span>
                      </th>
                      <th className="text-right px-3 py-3 text-xs font-medium uppercase tracking-wider cursor-pointer" style={{ color: "var(--page-text-muted)" }}
                        onClick={() => handleSort("reach")}>
                        <span className="flex items-center justify-end gap-1">Engagement <SortIcon field="reach" /></span>
                      </th>
                      <th className="text-right px-3 py-3 text-xs font-medium uppercase tracking-wider cursor-pointer" style={{ color: "var(--page-text-muted)" }}
                        onClick={() => handleSort("engagement_rate")}>
                        <span className="flex items-center justify-end gap-1">Eng. Rate <SortIcon field="engagement_rate" /></span>
                      </th>
                      <th className="text-center px-5 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPosts.map((row: any, idx: number) => {
                      const PlatformIcon = platformIconMap[row.platform] ?? Eye;
                      return (
                        <motion.tr key={row.post_id || idx}
                          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 * idx }}
                          className="transition-colors hover:bg-[var(--sidebar-hover-bg)]"
                          style={{ borderBottom: "1px solid var(--surface-border)" }}>
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <div
                                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                                style={{ backgroundColor: "rgba(124,58,237,0.12)", border: "1px solid var(--surface-border)" }}
                              >
                                <BarChart3 className="h-4 w-4" style={{ color: SERIES.violet }} />
                              </div>
                              <p className="line-clamp-1 max-w-[240px] text-sm" style={{ color: "var(--page-text)" }}>{row.content}</p>
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-1.5">
                              <PlatformIcon className="h-3.5 w-3.5" />
                              <span className="text-xs capitalize" style={{ color: "var(--page-text-muted)" }}>{row.platform}</span>
                            </div>
                          </td>
                          <td className="px-3 py-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
                            {row.published_at ? formatDate(row.published_at) : "—"}
                          </td>
                          <td className="px-3 py-3 text-right text-sm font-semibold tabular-nums" style={{ color: "var(--page-heading)" }}>
                            {formatNumber(row.total_engagement || 0)}
                          </td>
                          <td className="px-3 py-3 text-right text-sm font-semibold tabular-nums" style={{ color: SERIES.emerald }}>
                            {row.engagement_rate != null ? `${(row.engagement_rate * 100).toFixed(2)}%` : "—"}
                          </td>
                          <td className="px-5 py-3 text-center">
                            <Badge variant="success" size="sm" dot>Published</Badge>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* Engagement Breakdown + Posting Heatmap */}
        {!loading && (
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Engagement Pie */}
            <motion.div variants={fadeUp}>
              <GlassCard padding="lg" className="h-full">
                <SectionHeader
                  icon={Heart}
                  accent={SERIES.amber}
                  title="Engagement Breakdown"
                  subtitle="Distribution by interaction type"
                />
                {engagementBreakdown.length > 0 ? (
                  <>
                    <div className="h-[240px] relative">
                      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                        <PieChart>
                          <Pie data={engagementBreakdown} cx="50%" cy="50%" innerRadius={70} outerRadius={100}
                            dataKey="value" stroke="none" paddingAngle={3}>
                            {engagementBreakdown.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip content={<PieTooltip />} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="text-center">
                          <p className="text-2xl font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>{formatNumber(totalEngagement)}</p>
                          <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Total</p>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mt-4">
                      {engagementBreakdown.map((item) => (
                        <div key={item.name} className="flex items-center gap-2 text-xs">
                          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
                          <span style={{ color: "var(--page-text-secondary)" }}>{item.name}</span>
                          <span className="ml-auto tabular-nums" style={{ color: "var(--page-text-muted)" }}>{formatNumber(item.value)}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="flex h-64 flex-col items-center justify-center gap-3" style={{ color: "var(--page-text-muted)" }}>
                    <Heart className="h-10 w-10 opacity-30" />
                    <p className="text-sm">No engagement data yet</p>
                  </div>
                )}
              </GlassCard>
            </motion.div>

            {/* Best Posting Times Heatmap */}
            <motion.div variants={fadeUp}>
              <GlassCard padding="lg" className="h-full">
                <SectionHeader
                  icon={Clock}
                  accent={SERIES.sky}
                  title="Best Posting Times"
                  subtitle="Estimated engagement intensity by day and hour"
                />
                <div className="overflow-x-auto">
                  <div className="min-w-[500px]">
                    <div className="flex mb-1">
                      <div className="w-9 flex-shrink-0" />
                      {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
                        <div key={h} className="flex-1 text-center text-[10px]" style={{ color: "var(--page-text-muted)" }}>
                          {h === 0 ? "12a" : h < 12 ? `${h}a` : h === 12 ? "12p" : `${h - 12}p`}
                        </div>
                      ))}
                    </div>
                    {DAYS.map((day, di) => (
                      <div key={day} className="flex items-center gap-0.5 mb-0.5">
                        <div className="w-9 flex-shrink-0 text-[10px]" style={{ color: "var(--page-text-muted)" }}>{day}</div>
                        {HOURS.map((_, hi) => (
                          <div key={hi} className={cn("flex-1 h-4 rounded-[2px] transition-all", getHeatColor(heatmapData[di][hi]))} />
                        ))}
                      </div>
                    ))}
                    <div className="flex items-center gap-2 mt-3 justify-end">
                      <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>Low</span>
                      {HEAT_SCALE.map((c) => (
                        <div key={c} className={cn("w-4 h-3 rounded-sm", c)} />
                      ))}
                      <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>High</span>
                    </div>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          </div>
        )}

        {/* AI Recommendations */}
        {!loading && platformBreakdown.length > 0 && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <SectionHeader
                icon={Sparkles}
                accent={SERIES.violet}
                title="AI Recommendations"
              />
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  {
                    icon: Clock,
                    title: "Optimal Posting Times",
                    description: "Your heatmap shows peak engagement during 10–11 AM on weekdays. Scheduling posts in this window can boost reach by up to 22%.",
                    impact: "+22% reach",
                    color: "#38bdf8", bg: "rgba(56,189,248,0.10)", border: "rgba(56,189,248,0.30)",
                  },
                  {
                    icon: Zap,
                    title: "Top Platform",
                    description: platformBreakdown.length > 0
                      ? `${platformBreakdown[0].platform.charAt(0).toUpperCase() + platformBreakdown[0].platform.slice(1)} drives the most reach. Double down on content for this platform.`
                      : "Focus your best content on your top-performing platform.",
                    impact: "Top channel",
                    color: "#7c3aed", bg: "rgba(124,58,237,0.10)", border: "rgba(124,58,237,0.30)",
                  },
                  {
                    icon: Lightbulb,
                    title: "Engagement Tip",
                    description: "Posts with questions and calls-to-action get 3× more comments. Try asking your audience a question in your next post.",
                    impact: "+3x comments",
                    color: "#10b981", bg: "rgba(16,185,129,0.10)", border: "rgba(16,185,129,0.30)",
                  },
                ].map((rec) => (
                  <div key={rec.title} className="rounded-xl p-4" style={{ background: rec.bg, border: `1px solid ${rec.border}` }}>
                    <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl" style={{ background: rec.bg }}>
                      <rec.icon className="h-5 w-5" style={{ color: rec.color }} />
                    </div>
                    <p className="mb-2 text-sm font-semibold" style={{ color: "var(--page-heading)" }}>{rec.title}</p>
                    <p className="mb-3 text-xs leading-relaxed" style={{ color: "var(--page-text-secondary)" }}>{rec.description}</p>
                    <span className="text-xs font-semibold" style={{ color: rec.color }}>{rec.impact}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </motion.div>
        )}
      </motion.div>
    </DashboardLayout>
  );
}
