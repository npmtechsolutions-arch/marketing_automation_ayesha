import { useState, useMemo } from "react";
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
  Lightbulb,
  Clock,
  Zap,
  BarChart3,
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

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

// ---------------------------------------------------------------------------
// Mock Data
// ---------------------------------------------------------------------------
type DateRange = "7d" | "30d" | "90d" | "custom";

function generateTrendData(days: number) {
  const data = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const base = 5000 + Math.sin(i * 0.3) * 2000;
    data.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      reach: Math.round(base + Math.random() * 3000),
      engagement: Math.round(base * 0.38 + Math.random() * 800),
      followers: Math.round(80 + Math.random() * 120),
      clicks: Math.round(base * 0.12 + Math.random() * 400),
    });
  }
  return data;
}

const trendDataMap: Record<string, ReturnType<typeof generateTrendData>> = {
  "7d": generateTrendData(7),
  "30d": generateTrendData(30),
  "90d": generateTrendData(90),
  custom: generateTrendData(30),
};

const platformComparison = [
  { name: "Instagram", likes: 12400, comments: 3200, shares: 1800, color: "#E4405F" },
  { name: "LinkedIn", likes: 8900, comments: 2400, shares: 3100, color: "#0A66C2" },
  { name: "Twitter", likes: 7200, comments: 1800, shares: 4200, color: "#1DA1F2" },
  { name: "Facebook", likes: 6100, comments: 1500, shares: 980, color: "#1877F2" },
  { name: "YouTube", likes: 4500, comments: 2100, shares: 750, color: "#FF0000" },
];

const contentPerformance = [
  { id: 1, content: "AI-powered content scheduler launch announcement", platform: "linkedin", date: "2026-03-28", reach: 45200, engagement: 6800, ctr: 4.2, status: "published" },
  { id: 2, content: "5 marketing automation trends for 2026 thread", platform: "twitter", date: "2026-03-27", reach: 38100, engagement: 5400, ctr: 3.8, status: "published" },
  { id: 3, content: "Behind the scenes product photoshoot carousel", platform: "instagram", date: "2026-03-26", reach: 52300, engagement: 8200, ctr: 5.1, status: "published" },
  { id: 4, content: "50K followers milestone celebration post", platform: "facebook", date: "2026-03-25", reach: 28400, engagement: 4100, ctr: 2.9, status: "published" },
  { id: 5, content: "Organic growth case study breakdown", platform: "linkedin", date: "2026-03-24", reach: 33700, engagement: 5600, ctr: 3.5, status: "published" },
  { id: 6, content: "Quick tip: Contrarian posting times work better", platform: "twitter", date: "2026-03-23", reach: 21500, engagement: 3200, ctr: 2.7, status: "published" },
  { id: 7, content: "New feature teaser video for Instagram Reels", platform: "instagram", date: "2026-03-22", reach: 67800, engagement: 12400, ctr: 6.3, status: "published" },
  { id: 8, content: "Weekly marketing automation newsletter recap", platform: "linkedin", date: "2026-03-21", reach: 18900, engagement: 2800, ctr: 2.1, status: "published" },
  { id: 9, content: "Customer testimonial video compilation", platform: "youtube", date: "2026-03-20", reach: 24600, engagement: 4300, ctr: 3.9, status: "published" },
  { id: 10, content: "Industry report infographic with key stats", platform: "facebook", date: "2026-03-19", reach: 15200, engagement: 2100, ctr: 1.8, status: "published" },
];

const engagementBreakdown = [
  { name: "Likes", value: 48200, color: "#A855F7" },
  { name: "Comments", value: 15800, color: "#3B82F6" },
  { name: "Shares", value: 9400, color: "#10B981" },
  { name: "Saves", value: 6200, color: "#EC4899" },
];

const totalEngagement = engagementBreakdown.reduce((s, d) => s + d.value, 0);

// Best posting times heatmap data (7 days x 24 hours)
const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const hours = Array.from({ length: 24 }, (_, i) => i);

function generateHeatmapData() {
  return days.map((day) =>
    hours.map((hour) => {
      // Simulate higher engagement during work hours and certain days
      let base = 10;
      if (hour >= 9 && hour <= 17) base += 40;
      if (hour >= 10 && hour <= 12) base += 25;
      if (day === "Tue" || day === "Thu") base += 20;
      if (day === "Sat" || day === "Sun") base -= 15;
      if (hour >= 0 && hour <= 5) base = 5;
      return Math.max(0, Math.min(100, base + Math.round(Math.random() * 20 - 10)));
    })
  );
}

const heatmapData = generateHeatmapData();

const aiRecommendations = [
  {
    id: 1,
    icon: Clock,
    title: "Shift posting schedule to 10-11 AM on weekdays",
    description: "Your heatmap shows peak engagement during mid-morning hours. Moving 3 weekly posts earlier could boost reach by 22%.",
    impact: "+22% reach",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  {
    id: 2,
    icon: Sparkles,
    title: "Increase video content ratio to 60%",
    description: "Your video posts consistently outperform static images by 3.2x. Instagram Reels and LinkedIn videos drive the most engagement.",
    impact: "+3.2x engagement",
    color: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
  },
  {
    id: 3,
    icon: Lightbulb,
    title: "Leverage LinkedIn for thought leadership content",
    description: "LinkedIn shows the highest CTR at 3.5%. Long-form articles and industry insights resonate strongly with your audience.",
    impact: "+35% CTR",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
];

const platformIconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter,
  facebook: Facebook,
  youtube: Youtube,
};

type TrendMetric = "reach" | "engagement" | "followers" | "clicks";
type SortField = "reach" | "engagement" | "ctr" | "date";
type SortDirection = "asc" | "desc";

// ---------------------------------------------------------------------------
// Custom Recharts tooltips
// ---------------------------------------------------------------------------
function GlassTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl backdrop-blur-xl bg-slate-900/90 border border-white/10 px-4 py-3 shadow-2xl">
      <p className="text-xs text-gray-400 mb-2 font-medium">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-sm">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-gray-300 capitalize">{entry.dataKey}:</span>
          <span className="font-semibold text-white">
            {formatNumber(entry.value)}
          </span>
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
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: d.payload.color }}
        />
        <span className="text-gray-300">{d.name}:</span>
        <span className="font-semibold text-white">
          {formatNumber(d.value)}
        </span>
      </div>
      <p className="text-[11px] text-gray-500 mt-1">
        {((d.value / totalEngagement) * 100).toFixed(1)}% of total
      </p>
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
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.fill }}
          />
          <span className="text-gray-300 capitalize">{entry.dataKey}:</span>
          <span className="font-semibold text-white">
            {formatNumber(entry.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Heatmap color helper
// ---------------------------------------------------------------------------
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
  const [sortField, setSortField] = useState<SortField>("reach");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  const trendData = trendDataMap[dateRange];

  const sortedContent = useMemo(() => {
    return [...contentPerformance].sort((a, b) => {
      const aVal = sortField === "date" ? new Date(a.date).getTime() : a[sortField];
      const bVal = sortField === "date" ? new Date(b.date).getTime() : b[sortField];
      return sortDir === "desc" ? (bVal as number) - (aVal as number) : (aVal as number) - (bVal as number);
    });
  }, [sortField, sortDir]);

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 text-gray-600" />;
    return sortDir === "desc" ? (
      <ArrowDown className="w-3 h-3 text-purple-400" />
    ) : (
      <ArrowUp className="w-3 h-3 text-purple-400" />
    );
  }

  const metricColors: Record<TrendMetric, { stroke: string; id: string }> = {
    reach: { stroke: "#A855F7", id: "gradAnalyticsReach" },
    engagement: { stroke: "#3B82F6", id: "gradAnalyticsEng" },
    followers: { stroke: "#10B981", id: "gradAnalyticsFollow" },
    clicks: { stroke: "#F59E0B", id: "gradAnalyticsClicks" },
  };

  const metricTabs: { key: TrendMetric; label: string }[] = [
    { key: "reach", label: "Reach" },
    { key: "engagement", label: "Engagement" },
    { key: "followers", label: "Followers" },
    { key: "clicks", label: "Clicks" },
  ];

  const dateRanges: { key: DateRange; label: string }[] = [
    { key: "7d", label: "7d" },
    { key: "30d", label: "30d" },
    { key: "90d", label: "90d" },
    { key: "custom", label: "Custom" },
  ];

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6 pb-8"
      >
        {/* ----------------------------------------------------------------- */}
        {/* Header */}
        {/* ----------------------------------------------------------------- */}
        <motion.div
          variants={fadeUp}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold text-white sm:text-3xl">
              Analytics
            </h1>
            <p className="mt-1 text-sm text-gray-400">
              Track performance across all your platforms
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
              {dateRanges.map((dr) => (
                <button
                  key={dr.key}
                  onClick={() => setDateRange(dr.key)}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200",
                    dateRange === dr.key
                      ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20 shadow-lg shadow-purple-500/5"
                      : "text-gray-400 hover:text-white"
                  )}
                >
                  {dr.label}
                </button>
              ))}
            </div>
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="w-4 h-4" />}
            >
              Export Report
            </Button>
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Stats Row */}
        {/* ----------------------------------------------------------------- */}
        <motion.div
          variants={staggerContainer}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
        >
          <motion.div variants={fadeUp}>
            <StatCard
              label="Total Reach"
              value="284.5K"
              change={14.2}
              changeLabel="vs last period"
              icon={<Eye className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Total Engagement"
              value="79.6K"
              change={9.8}
              changeLabel="vs last period"
              icon={<Heart className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Avg Engagement Rate"
              value="5.42%"
              change={1.3}
              changeLabel="vs last period"
              icon={<TrendingUp className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Click-Through Rate"
              value="3.18%"
              change={-0.4}
              changeLabel="vs last period"
              icon={<MousePointerClick className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="New Followers"
              value="4,312"
              change={18.5}
              changeLabel="vs last period"
              icon={<UserPlus className="w-5 h-5" />}
            />
          </motion.div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Performance Trends Chart */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Performance Trends
                </h2>
                <p className="text-sm text-gray-400 mt-0.5">
                  Track key metrics over time
                </p>
              </div>

              <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
                {metricTabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveMetric(tab.key)}
                    className={cn(
                      "px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200",
                      activeMetric === tab.key
                        ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20 shadow-lg shadow-purple-500/5"
                        : "text-gray-400 hover:text-white"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-[360px] -mx-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    {Object.entries(metricColors).map(([_key, val]) => (
                      <linearGradient
                        key={val.id}
                        id={val.id}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={val.stroke}
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="100%"
                          stopColor={val.stroke}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#6B7280", fontSize: 11 }}
                    dy={8}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#6B7280", fontSize: 11 }}
                    tickFormatter={(v: number) => formatNumber(v)}
                    dx={-8}
                    width={50}
                  />
                  <Tooltip content={<GlassTooltip />} />
                  <Area
                    type="monotone"
                    dataKey={activeMetric}
                    stroke={metricColors[activeMetric].stroke}
                    strokeWidth={2.5}
                    fill={`url(#${metricColors[activeMetric].id})`}
                    dot={false}
                    activeDot={{
                      r: 5,
                      fill: metricColors[activeMetric].stroke,
                      stroke: "#1E1B4B",
                      strokeWidth: 2,
                    }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Platform Comparison */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-white">
                Platform Comparison
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Engagement breakdown by platform
              </p>
            </div>

            <div className="flex items-center gap-6 mb-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-purple-500" />
                <span className="text-xs text-gray-400">Likes</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-blue-500" />
                <span className="text-xs text-gray-400">Comments</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-xs text-gray-400">Shares</span>
              </div>
            </div>

            <div className="h-[300px] -mx-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={platformComparison}
                  layout="vertical"
                  barCategoryGap="20%"
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#6B7280", fontSize: 11 }}
                    tickFormatter={(v: number) => formatNumber(v)}
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#D1D5DB", fontSize: 12 }}
                    width={80}
                  />
                  <Tooltip content={<BarTooltip />} />
                  <Bar
                    dataKey="likes"
                    stackId="a"
                    fill="#A855F7"
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="comments"
                    stackId="a"
                    fill="#3B82F6"
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="shares"
                    stackId="a"
                    fill="#10B981"
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Content Performance Table */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-white">
                Content Performance
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Click column headers to sort
              </p>
            </div>

            <div className="overflow-x-auto -mx-5">
              <table className="w-full min-w-[700px]">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left px-5 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Content
                    </th>
                    <th className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Platform
                    </th>
                    <th
                      className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors"
                      onClick={() => handleSort("date")}
                    >
                      <span className="flex items-center gap-1">
                        Date <SortIcon field="date" />
                      </span>
                    </th>
                    <th
                      className="text-right px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors"
                      onClick={() => handleSort("reach")}
                    >
                      <span className="flex items-center justify-end gap-1">
                        Reach <SortIcon field="reach" />
                      </span>
                    </th>
                    <th
                      className="text-right px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors"
                      onClick={() => handleSort("engagement")}
                    >
                      <span className="flex items-center justify-end gap-1">
                        Engagement <SortIcon field="engagement" />
                      </span>
                    </th>
                    <th
                      className="text-right px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors"
                      onClick={() => handleSort("ctr")}
                    >
                      <span className="flex items-center justify-end gap-1">
                        CTR <SortIcon field="ctr" />
                      </span>
                    </th>
                    <th className="text-center px-5 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedContent.map((row, idx) => {
                    const PlatformIcon = platformIconMap[row.platform] ?? Eye;
                    return (
                      <motion.tr
                        key={row.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.05 * idx }}
                        className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-white/10 flex items-center justify-center flex-shrink-0">
                              <BarChart3 className="w-4 h-4 text-purple-400" />
                            </div>
                            <p className="text-sm text-gray-300 line-clamp-1 max-w-[240px]">
                              {row.content}
                            </p>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5">
                            <PlatformIcon className="w-3.5 h-3.5 text-gray-400" />
                            <span className="text-xs text-gray-400 capitalize">
                              {row.platform}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-xs text-gray-400">
                          {formatDate(row.date)}
                        </td>
                        <td className="px-3 py-3 text-right text-sm font-medium text-white">
                          {formatNumber(row.reach)}
                        </td>
                        <td className="px-3 py-3 text-right text-sm font-medium text-white">
                          {formatNumber(row.engagement)}
                        </td>
                        <td className="px-3 py-3 text-right text-sm font-medium text-white">
                          {row.ctr}%
                        </td>
                        <td className="px-5 py-3 text-center">
                          <Badge variant="success" size="sm" dot>
                            Published
                          </Badge>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Engagement Breakdown + Best Posting Times Heatmap */}
        {/* ----------------------------------------------------------------- */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Engagement Pie */}
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg" className="h-full">
              <h2 className="text-lg font-semibold text-white mb-1">
                Engagement Breakdown
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                Distribution by interaction type
              </p>

              <div className="h-[240px] relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={engagementBreakdown}
                      cx="50%"
                      cy="50%"
                      innerRadius={70}
                      outerRadius={100}
                      dataKey="value"
                      stroke="none"
                      paddingAngle={3}
                    >
                      {engagementBreakdown.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-white">
                      {formatNumber(totalEngagement)}
                    </p>
                    <p className="text-[10px] text-gray-500 uppercase tracking-wider">
                      Total
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-4">
                {engagementBreakdown.map((item) => (
                  <div
                    key={item.name}
                    className="flex items-center gap-2 text-xs"
                  >
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-gray-400">{item.name}</span>
                    <span className="text-gray-500 ml-auto">
                      {formatNumber(item.value)}
                    </span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </motion.div>

          {/* Best Posting Times Heatmap */}
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg" className="h-full">
              <h2 className="text-lg font-semibold text-white mb-1">
                Best Posting Times
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                Engagement intensity by day and hour
              </p>

              <div className="overflow-x-auto">
                <div className="min-w-[480px]">
                  {/* Hour labels */}
                  <div className="flex ml-10 mb-1">
                    {hours
                      .filter((h) => h % 3 === 0)
                      .map((h) => (
                        <div
                          key={h}
                          className="text-[9px] text-gray-500 text-center"
                          style={{ width: `${(3 / 24) * 100}%` }}
                        >
                          {h === 0
                            ? "12a"
                            : h < 12
                            ? `${h}a`
                            : h === 12
                            ? "12p"
                            : `${h - 12}p`}
                        </div>
                      ))}
                  </div>

                  {/* Heatmap grid */}
                  {days.map((day, dayIdx) => (
                    <div key={day} className="flex items-center gap-1 mb-0.5">
                      <span className="text-[10px] text-gray-500 w-8 text-right flex-shrink-0">
                        {day}
                      </span>
                      <div className="flex-1 flex gap-[1px]">
                        {hours.map((hour) => (
                          <div
                            key={`${day}-${hour}`}
                            className={cn(
                              "flex-1 aspect-square rounded-[2px] transition-colors",
                              getHeatColor(heatmapData[dayIdx][hour])
                            )}
                            title={`${day} ${hour}:00 - Score: ${heatmapData[dayIdx][hour]}`}
                          />
                        ))}
                      </div>
                    </div>
                  ))}

                  {/* Legend */}
                  <div className="flex items-center justify-end gap-1 mt-3">
                    <span className="text-[9px] text-gray-500 mr-1">Low</span>
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/5" />
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/15" />
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/30" />
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/50" />
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/70" />
                    <div className="w-4 h-3 rounded-[2px] bg-purple-500/90" />
                    <span className="text-[9px] text-gray-500 ml-1">High</span>
                  </div>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* AI Recommendations */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg" glow>
            <div className="flex items-center gap-2 mb-5">
              <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  AI Recommendations
                </h2>
                <p className="text-xs text-gray-500">
                  Actionable insights based on your data
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {aiRecommendations.map((rec, idx) => {
                const Icon = rec.icon;
                return (
                  <motion.div
                    key={rec.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + idx * 0.1 }}
                    className={cn(
                      "rounded-xl p-4 border-l-[3px] bg-white/[0.02] hover:bg-white/[0.04] transition-colors",
                      rec.border
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={cn(
                          "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
                          rec.bg
                        )}
                      >
                        <Icon className={cn("w-4 h-4", rec.color)} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white leading-snug">
                          {rec.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                          {rec.description}
                        </p>
                        <div className="flex items-center gap-2 mt-3">
                          <Badge variant="success" size="sm">
                            {rec.impact}
                          </Badge>
                          <button className="text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1">
                            <Zap className="w-3 h-3" /> Apply
                          </button>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </GlassCard>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
