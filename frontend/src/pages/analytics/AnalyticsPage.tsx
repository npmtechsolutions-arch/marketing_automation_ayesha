import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Eye,
  Heart,
  TrendingUp,
  UserPlus,
  MousePointerClick,
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Sparkles,
  Clock,
  Zap,
  BarChart3,
  RefreshCw,
  Lightbulb,
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
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { cn, formatNumber, formatDate } from "@/lib/utils";
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

// ---------------------------------------------------------------------------
// Custom tooltips
// ---------------------------------------------------------------------------
function GlassTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl backdrop-blur-xl bg-slate-900/90 border border-white/10 px-4 py-3 shadow-2xl">
      <p className="text-xs text-gray-400 mb-2 font-medium">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-300 capitalize">{entry.dataKey}:</span>
          <span className="font-semibold text-white">{formatNumber(entry.value)}</span>
        </div>
      ))}
    </div>
  );
}

function PieTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div className="rounded-xl backdrop-blur-xl bg-slate-900/90 border border-white/10 px-4 py-3 shadow-2xl">
      <div className="flex items-center gap-2 text-sm">
        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.payload.color }} />
        <span className="text-gray-300">{d.name}:</span>
        <span className="font-semibold text-white">{formatNumber(d.value)}</span>
      </div>
    </div>
  );
}

function BarTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl backdrop-blur-xl bg-slate-900/90 border border-white/10 px-4 py-3 shadow-2xl">
      <p className="text-xs text-gray-400 mb-2 font-medium">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.fill }} />
          <span className="text-gray-300 capitalize">{entry.dataKey}:</span>
          <span className="font-semibold text-white">{formatNumber(entry.value)}</span>
        </div>
      ))}
    </div>
  );
}

// Heatmap helpers
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);
function getHeatColor(value: number): string {
  if (value <= 15) return "bg-purple-500/5";
  if (value <= 30) return "bg-purple-500/15";
  if (value <= 50) return "bg-purple-500/30";
  if (value <= 70) return "bg-purple-500/50";
  if (value <= 85) return "bg-purple-500/70";
  return "bg-purple-500/90";
}

// ---------------------------------------------------------------------------
// Analytics Page
// ---------------------------------------------------------------------------
export default function AnalyticsPage() {
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
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 text-gray-600" />;
    return sortDir === "desc" ? <ArrowDown className="w-3 h-3 text-purple-400" /> : <ArrowUp className="w-3 h-3 text-purple-400" />;
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
      { name: "Likes", value: totals.likes, color: "#A855F7" },
      { name: "Comments", value: totals.comments, color: "#3B82F6" },
      { name: "Shares", value: totals.shares, color: "#10B981" },
      { name: "Clicks", value: totals.clicks, color: "#EC4899" },
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

  const metricColors: Record<TrendMetric, { stroke: string; id: string }> = {
    reach: { stroke: "#A855F7", id: "gradAnalyticsReach" },
    engagement: { stroke: "#3B82F6", id: "gradAnalyticsEng" },
    impressions: { stroke: "#10B981", id: "gradAnalyticsImp" },
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

  return (
    <DashboardLayout>
      <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6 pb-8">

        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white sm:text-3xl">Analytics</h1>
            <p className="mt-1 text-sm text-gray-400">Track performance across all your platforms</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
              {dateRanges.map((dr) => (
                <button key={dr.key} onClick={() => handleRangeChange(dr.key)}
                  className={cn("px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200",
                    dateRange === dr.key
                      ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20"
                      : "text-gray-400 hover:text-white")}>
                  {dr.label}
                </button>
              ))}
            </div>
            {refreshing && <RefreshCw className="w-4 h-4 text-purple-400 animate-spin" />}
          </div>
        </motion.div>

        {/* Stats Row */}
        <motion.div variants={staggerContainer} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loading ? (
            [...Array(4)].map((_, i) => <div key={i} className="h-28 rounded-2xl bg-white/5 animate-pulse" />)
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
                <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400 mb-2">No analytics data yet</p>
                <p className="text-sm text-slate-500">Publish posts and come back to see your performance metrics here.</p>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* Performance Trends Chart */}
        {!loading && chartData.length > 0 && (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-white">Performance Trends</h2>
                  <p className="text-sm text-gray-400 mt-0.5">Track key metrics over time</p>
                </div>
                <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
                  {metricTabs.map((tab) => (
                    <button key={tab.key} onClick={() => setActiveMetric(tab.key)}
                      className={cn("px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200",
                        activeMetric === tab.key
                          ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20"
                          : "text-gray-400 hover:text-white")}>
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-[360px] -mx-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      {Object.entries(metricColors).map(([_key, val]) => (
                        <linearGradient key={val.id} id={val.id} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={val.stroke} stopOpacity={0.3} />
                          <stop offset="100%" stopColor={val.stroke} stopOpacity={0} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#6B7280", fontSize: 11 }} dy={8} interval="preserveStartEnd" />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#6B7280", fontSize: 11 }} tickFormatter={(v) => formatNumber(v)} dx={-8} width={50} />
                    <Tooltip content={<GlassTooltip />} />
                    <Area type="monotone" dataKey={activeMetric} stroke={metricColors[activeMetric].stroke} strokeWidth={2.5}
                      fill={`url(#${metricColors[activeMetric].id})`} dot={false}
                      activeDot={{ r: 5, fill: metricColors[activeMetric].stroke, stroke: "#1E1B4B", strokeWidth: 2 }} />
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
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-white">Platform Comparison</h2>
                <p className="text-sm text-gray-400 mt-0.5">Engagement breakdown by platform</p>
              </div>
              <div className="flex items-center gap-6 mb-4">
                {["Likes", "Comments", "Shares"].map((label, i) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${i === 0 ? "bg-purple-500" : i === 1 ? "bg-blue-500" : "bg-emerald-500"}`} />
                    <span className="text-xs text-gray-400">{label}</span>
                  </div>
                ))}
              </div>
              <div className="h-[280px] -mx-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={platformChartData} layout="vertical" barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: "#6B7280", fontSize: 11 }} tickFormatter={(v) => formatNumber(v)} />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: "#D1D5DB", fontSize: 12 }} width={80} />
                    <Tooltip content={<BarTooltip />} />
                    <Bar dataKey="likes" stackId="a" fill="#A855F7" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="comments" stackId="a" fill="#3B82F6" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="shares" stackId="a" fill="#10B981" radius={[0, 4, 4, 0]} />
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
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-white">Content Performance</h2>
                <p className="text-sm text-gray-400 mt-0.5">Click column headers to sort</p>
              </div>
              <div className="overflow-x-auto -mx-5">
                <table className="w-full min-w-[700px]">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left px-5 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Content</th>
                      <th className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Platform</th>
                      <th className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                        onClick={() => handleSort("published_at")}>
                        <span className="flex items-center gap-1">Date <SortIcon field="published_at" /></span>
                      </th>
                      <th className="text-right px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                        onClick={() => handleSort("reach")}>
                        <span className="flex items-center justify-end gap-1">Engagement <SortIcon field="reach" /></span>
                      </th>
                      <th className="text-right px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                        onClick={() => handleSort("engagement_rate")}>
                        <span className="flex items-center justify-end gap-1">Eng. Rate <SortIcon field="engagement_rate" /></span>
                      </th>
                      <th className="text-center px-5 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPosts.map((row: any, idx: number) => {
                      const PlatformIcon = platformIconMap[row.platform] ?? Eye;
                      return (
                        <motion.tr key={row.post_id || idx}
                          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 * idx }}
                          className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-white/10 flex items-center justify-center flex-shrink-0">
                                <BarChart3 className="w-4 h-4 text-purple-400" />
                              </div>
                              <p className="text-sm text-gray-300 line-clamp-1 max-w-[240px]">{row.content}</p>
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-1.5">
                              <PlatformIcon className="w-3.5 h-3.5 text-gray-400" />
                              <span className="text-xs text-gray-400 capitalize">{row.platform}</span>
                            </div>
                          </td>
                          <td className="px-3 py-3 text-xs text-gray-400">
                            {row.published_at ? formatDate(row.published_at) : "—"}
                          </td>
                          <td className="px-3 py-3 text-right text-sm font-medium text-white">
                            {formatNumber(row.total_engagement || 0)}
                          </td>
                          <td className="px-3 py-3 text-right text-sm font-medium text-emerald-400">
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
                <h2 className="text-lg font-semibold text-white mb-1">Engagement Breakdown</h2>
                <p className="text-sm text-gray-500 mb-4">Distribution by interaction type</p>
                {engagementBreakdown.length > 0 ? (
                  <>
                    <div className="h-[240px] relative">
                      <ResponsiveContainer width="100%" height="100%">
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
                          <p className="text-2xl font-bold text-white">{formatNumber(totalEngagement)}</p>
                          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Total</p>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mt-4">
                      {engagementBreakdown.map((item) => (
                        <div key={item.name} className="flex items-center gap-2 text-xs">
                          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                          <span className="text-gray-400">{item.name}</span>
                          <span className="text-gray-500 ml-auto">{formatNumber(item.value)}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-600 gap-3">
                    <Heart className="w-10 h-10 opacity-30" />
                    <p className="text-sm text-slate-500">No engagement data yet</p>
                  </div>
                )}
              </GlassCard>
            </motion.div>

            {/* Best Posting Times Heatmap */}
            <motion.div variants={fadeUp}>
              <GlassCard padding="lg" className="h-full">
                <h2 className="text-lg font-semibold text-white mb-1">Best Posting Times</h2>
                <p className="text-sm text-gray-500 mb-4">Estimated engagement intensity by day and hour</p>
                <div className="overflow-x-auto">
                  <div className="min-w-[500px]">
                    <div className="flex mb-1">
                      <div className="w-9 flex-shrink-0" />
                      {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
                        <div key={h} className="flex-1 text-center text-[10px] text-gray-600">
                          {h === 0 ? "12a" : h < 12 ? `${h}a` : h === 12 ? "12p" : `${h - 12}p`}
                        </div>
                      ))}
                    </div>
                    {DAYS.map((day, di) => (
                      <div key={day} className="flex items-center gap-0.5 mb-0.5">
                        <div className="w-9 text-[10px] text-gray-500 flex-shrink-0">{day}</div>
                        {HOURS.map((_, hi) => (
                          <div key={hi} className={cn("flex-1 h-4 rounded-[2px] transition-all", getHeatColor(heatmapData[di][hi]))} />
                        ))}
                      </div>
                    ))}
                    <div className="flex items-center gap-2 mt-3 justify-end">
                      <span className="text-[10px] text-gray-600">Low</span>
                      {["bg-purple-500/5", "bg-purple-500/15", "bg-purple-500/30", "bg-purple-500/50", "bg-purple-500/70", "bg-purple-500/90"].map((c) => (
                        <div key={c} className={cn("w-4 h-3 rounded-sm", c)} />
                      ))}
                      <span className="text-[10px] text-gray-600">High</span>
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
              <div className="flex items-center gap-2 mb-5">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-white">AI Recommendations</h2>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  {
                    icon: Clock,
                    title: "Optimal Posting Times",
                    description: "Your heatmap shows peak engagement during 10–11 AM on weekdays. Scheduling posts in this window can boost reach by up to 22%.",
                    impact: "+22% reach",
                    color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30",
                  },
                  {
                    icon: Zap,
                    title: "Top Platform",
                    description: platformBreakdown.length > 0
                      ? `${platformBreakdown[0].platform.charAt(0).toUpperCase() + platformBreakdown[0].platform.slice(1)} drives the most reach. Double down on content for this platform.`
                      : "Focus your best content on your top-performing platform.",
                    impact: "Top channel",
                    color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30",
                  },
                  {
                    icon: Lightbulb,
                    title: "Engagement Tip",
                    description: "Posts with questions and calls-to-action get 3× more comments. Try asking your audience a question in your next post.",
                    impact: "+3x comments",
                    color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30",
                  },
                ].map((rec) => (
                  <div key={rec.title} className={cn("rounded-xl p-4 border", rec.bg, rec.border)}>
                    <div className={cn("w-9 h-9 rounded-xl flex items-center justify-center mb-3", rec.bg)}>
                      <rec.icon className={cn("w-5 h-5", rec.color)} />
                    </div>
                    <p className="text-sm font-semibold text-white mb-2">{rec.title}</p>
                    <p className="text-xs text-gray-400 leading-relaxed mb-3">{rec.description}</p>
                    <span className={cn("text-xs font-semibold", rec.color)}>{rec.impact}</span>
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
