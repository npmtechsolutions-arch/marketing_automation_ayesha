import { useState } from "react";
import { motion } from "framer-motion";
import {
  Eye,
  Heart,
  TrendingUp,
  TrendingDown,
  Plus,
  CalendarDays,
  Sparkles,
  Clock,
  PlayCircle,
  Lightbulb,
  ThumbsUp,
  MessageCircle,
  Share2,
  ArrowUpRight,
  ChevronRight,
  Zap,
  Send,
  Brain,
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
} from "recharts";
import { Instagram, Linkedin, Twitter, Facebook, Youtube } from "@/components/shared/SocialIcons";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn, formatNumber, formatDate } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Mock Data
// ---------------------------------------------------------------------------
const username = "Alex";

function generatePerformanceData(days: number) {
  const data = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const base = 4000 + Math.sin(i * 0.4) * 1500;
    data.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      reach: Math.round(base + Math.random() * 2000),
      engagement: Math.round(base * 0.35 + Math.random() * 600),
    });
  }
  return data;
}

const performanceDataMap: Record<string, ReturnType<typeof generatePerformanceData>> = {
  "7d": generatePerformanceData(7),
  "30d": generatePerformanceData(30),
  "90d": generatePerformanceData(90),
};

const statCards = [
  {
    label: "Total Reach",
    value: "143.2K",
    change: 12.5,
    changeLabel: "vs last month",
    icon: Eye,
    accentColor: "#7c3aed",
    gradientFrom: "#7c3aed",
    gradientTo: "#a78bfa",
    sparkline: [30, 45, 38, 55, 48, 62, 58, 70, 65, 80],
  },
  {
    label: "Engagement",
    value: "75.3K",
    change: 8.3,
    changeLabel: "vs last month",
    icon: Heart,
    accentColor: "#ec4899",
    gradientFrom: "#ec4899",
    gradientTo: "#f472b6",
    sparkline: [25, 35, 42, 38, 50, 45, 58, 52, 60, 68],
  },
  {
    label: "Growth Rate",
    value: "5.24%",
    change: 2.1,
    changeLabel: "vs last month",
    icon: TrendingUp,
    accentColor: "#f97316",
    gradientFrom: "#f97316",
    gradientTo: "#fb923c",
    sparkline: [20, 28, 35, 30, 42, 38, 45, 50, 55, 52],
  },
  {
    label: "Active Posts",
    value: "2,847",
    change: 15.7,
    changeLabel: "vs last month",
    icon: Send,
    accentColor: "#3b82f6",
    gradientFrom: "#3b82f6",
    gradientTo: "#60a5fa",
    sparkline: [35, 40, 38, 50, 55, 48, 60, 65, 58, 72],
  },
];

const topPosts = [
  {
    id: 1,
    content: "Just launched our new AI-powered content scheduler! Here's how it can save you 10+ hours a week on social media management...",
    platform: "linkedin",
    likes: 1284,
    comments: 156,
    shares: 89,
    date: "2026-03-28",
  },
  {
    id: 2,
    content: "5 marketing automation trends that will dominate 2026. Thread incoming...",
    platform: "twitter",
    likes: 2431,
    comments: 312,
    shares: 567,
    date: "2026-03-27",
  },
  {
    id: 3,
    content: "Behind the scenes of our product photoshoot! Swipe to see the final results vs the raw shots.",
    platform: "instagram",
    likes: 3892,
    comments: 234,
    shares: 145,
    date: "2026-03-26",
  },
  {
    id: 4,
    content: "Big news! We just crossed 50K followers. Thank you for being part of this incredible journey. Giveaway coming soon...",
    platform: "facebook",
    likes: 1567,
    comments: 423,
    shares: 201,
    date: "2026-03-25",
  },
  {
    id: 5,
    content: "How we grew from 0 to 100K organic reach in 3 months using our own tool. Full breakdown inside.",
    platform: "linkedin",
    likes: 987,
    comments: 178,
    shares: 312,
    date: "2026-03-24",
  },
];

const aiInsights = [
  {
    id: 1,
    icon: Clock,
    title: "Best posting time is 10:00 AM on Tuesday",
    description: "Your audience is most active mid-morning. Shifting posts earlier could boost reach by 18%.",
    accentColor: "#3b82f6",
    gradientFrom: "#3b82f6",
    gradientTo: "#60a5fa",
  },
  {
    id: 2,
    icon: PlayCircle,
    title: "Video content gets 3x more engagement",
    description: "Short-form videos under 60s outperform static images consistently across all your platforms.",
    accentColor: "#7c3aed",
    gradientFrom: "#7c3aed",
    gradientTo: "#a78bfa",
  },
  {
    id: 3,
    icon: TrendingUp,
    title: "LinkedIn audience grew 25% this month",
    description: "Your professional content strategy is paying off. Consider repurposing top posts as articles.",
    accentColor: "#10b981",
    gradientFrom: "#10b981",
    gradientTo: "#34d399",
  },
  {
    id: 4,
    icon: Lightbulb,
    title: "Consider increasing Instagram Reels",
    description: "Competitors are posting 3x more Reels. You could capture 40% more impressions with short videos.",
    accentColor: "#f97316",
    gradientFrom: "#f97316",
    gradientTo: "#fb923c",
  },
];

const platformBreakdown = [
  { name: "Facebook", icon: Facebook, color: "#1877F2", reach: 21800, engagement: 2.9, growth: -3.2, share: 45 },
  { name: "Instagram", icon: Instagram, color: "#E4405F", reach: 45200, engagement: 6.2, growth: 12.3, share: 85 },
  { name: "LinkedIn", icon: Linkedin, color: "#0A66C2", reach: 32100, engagement: 4.8, growth: 25.1, share: 68 },
  { name: "Twitter", icon: Twitter, color: "#1DA1F2", reach: 28400, engagement: 3.5, growth: 8.7, share: 58 },
  { name: "YouTube", icon: Youtube, color: "#FF0000", reach: 15600, engagement: 7.1, growth: 18.5, share: 32 },
];

const engagementDistribution = [
  { name: "Likes", value: 48200, color: "#7c3aed" },
  { name: "Comments", value: 12800, color: "#ec4899" },
  { name: "Shares", value: 8900, color: "#f97316" },
  { name: "Saves", value: 5400, color: "#3b82f6" },
];

const totalEngagement = engagementDistribution.reduce((s, d) => s + d.value, 0);

const platformIconMap: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter,
  facebook: Facebook,
  youtube: Youtube,
};

const platformColorMap: Record<string, string> = {
  instagram: "#E4405F",
  linkedin: "#0A66C2",
  twitter: "#1DA1F2",
  facebook: "#1877F2",
  youtube: "#FF0000",
};

// ---------------------------------------------------------------------------
// Custom Recharts tooltips
// ---------------------------------------------------------------------------
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-4 py-3 shadow-2xl"
      style={{
        background: "var(--dropdown-bg)",
        border: "1px solid var(--surface-border)",
        backdropFilter: "blur(12px)",
      }}
    >
      <p className="text-xs mb-2 font-medium" style={{ color: "var(--page-text-muted)" }}>{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-sm">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="capitalize" style={{ color: "var(--page-text-secondary)" }}>{entry.dataKey}:</span>
          <span className="font-semibold" style={{ color: "var(--page-heading)" }}>
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
    <div
      className="rounded-xl px-4 py-3 shadow-2xl"
      style={{
        background: "var(--dropdown-bg)",
        border: "1px solid var(--surface-border)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="flex items-center gap-2 text-sm">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: d.payload.color }}
        />
        <span style={{ color: "var(--page-text-secondary)" }}>{d.name}:</span>
        <span className="font-semibold" style={{ color: "var(--page-heading)" }}>
          {formatNumber(d.value)}
        </span>
      </div>
      <p className="text-[11px] mt-1" style={{ color: "var(--page-text-muted)" }}>
        {((d.value / totalEngagement) * 100).toFixed(1)}% of total
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Period tab buttons
// ---------------------------------------------------------------------------
const periods = [
  { key: "7d", label: "7d" },
  { key: "30d", label: "30d" },
  { key: "90d", label: "90d" },
] as const;

// ---------------------------------------------------------------------------
// Card wrapper component
// ---------------------------------------------------------------------------
function Card({
  children,
  className,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("rounded-2xl p-6", className)}
      style={{
        background: "var(--surface-bg)",
        border: "1px solid var(--surface-border)",
        boxShadow: "var(--surface-shadow)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard Page
// ---------------------------------------------------------------------------
export default function DashboardPage() {
  const [activePeriod, setActivePeriod] = useState<string>("30d");
  const performanceData = performanceDataMap[activePeriod];

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        {/* ----------------------------------------------------------------- */}
        {/* Header */}
        {/* ----------------------------------------------------------------- */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl" style={{ color: "var(--page-heading)" }}>
              Welcome back, {username}!{" "}
              <motion.span
                animate={{ rotate: [0, 14, -8, 14, -4, 10, 0] }}
                transition={{ duration: 1.5, delay: 0.6 }}
                className="inline-block origin-[70%_80%]"
              >
                👋
              </motion.span>
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>{today}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="primary" icon={<Plus className="w-4 h-4" />}>
              Create Post
            </Button>
            <Button size="sm" variant="secondary" icon={<CalendarDays className="w-4 h-4" />}>
              View Calendar
            </Button>
            <Button size="sm" variant="secondary" icon={<Sparkles className="w-4 h-4" />}>
              Generate Strategy
            </Button>
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Stat Cards Row */}
        {/* ----------------------------------------------------------------- */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map((card, idx) => {
            const Icon = card.icon;
            const isPositive = card.change >= 0;
            return (
              <motion.div
                key={card.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: idx * 0.08 }}
              >
                <div
                  className="rounded-2xl p-5 group hover:shadow-lg transition-all duration-300 relative overflow-hidden"
                  style={{
                    background: "var(--surface-bg)",
                    border: "1px solid var(--surface-border)",
                    boxShadow: "var(--surface-shadow)",
                    borderLeft: `4px solid ${card.accentColor}`,
                  }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium" style={{ color: "var(--page-text-secondary)" }}>
                      {card.label}
                    </p>
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{
                        background: `linear-gradient(135deg, ${card.gradientFrom}20, ${card.gradientTo}15)`,
                        border: `1px solid ${card.accentColor}25`,
                      }}
                    >
                      <Icon className="w-5 h-5" style={{ color: card.accentColor }} />
                    </div>
                  </div>

                  <p className="text-2xl font-bold tracking-tight" style={{ color: "var(--page-heading)" }}>
                    {card.value}
                  </p>

                  <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-md"
                        style={{
                          color: isPositive ? "var(--accent-green)" : "var(--accent-red)",
                          background: isPositive ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
                        }}
                      >
                        {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {isPositive ? "+" : ""}{card.change}%
                      </span>
                      <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                        {card.changeLabel}
                      </span>
                    </div>
                  </div>

                  {/* Sparkline */}
                  <div className="flex items-end gap-[3px] mt-3 h-8">
                    {card.sparkline.map((h, i) => (
                      <div
                        key={i}
                        className="flex-1 rounded-sm transition-all duration-300"
                        style={{
                          height: `${h}%`,
                          background: `${card.accentColor}${i === card.sparkline.length - 1 ? "" : "40"}`,
                          opacity: 0.4 + (i / card.sparkline.length) * 0.6,
                        }}
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* Performance Chart */}
        {/* ----------------------------------------------------------------- */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <Card>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
                  Performance Overview
                </h2>
                <p className="text-sm mt-0.5" style={{ color: "var(--page-text-secondary)" }}>
                  Track your reach and engagement over time
                </p>
              </div>

              {/* Pill period selector */}
              <div
                className="flex items-center gap-1 p-1 rounded-xl"
                style={{
                  background: "var(--surface-bg-hover)",
                  border: "1px solid var(--surface-border)",
                }}
              >
                {periods.map((p) => (
                  <button
                    key={p.key}
                    onClick={() => setActivePeriod(p.key)}
                    className="px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-200"
                    style={{
                      background: activePeriod === p.key ? "var(--gradient-primary)" : "transparent",
                      color: activePeriod === p.key ? "#ffffff" : "var(--page-text-secondary)",
                      boxShadow: activePeriod === p.key ? "0 2px 8px rgba(124,58,237,0.25)" : "none",
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-6 mb-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: "#7c3aed" }} />
                <span className="text-xs" style={{ color: "var(--page-text-secondary)" }}>Reach</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: "#ec4899" }} />
                <span className="text-xs" style={{ color: "var(--page-text-secondary)" }}>Engagement</span>
              </div>
            </div>

            <div className="h-[320px] -mx-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={performanceData}>
                  <defs>
                    <linearGradient id="gradReach" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#7c3aed" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="gradEng" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ec4899" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#ec4899" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--surface-border)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "var(--page-text-muted)", fontSize: 11 }}
                    dy={8}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "var(--page-text-muted)", fontSize: 11 }}
                    tickFormatter={(v: number) => formatNumber(v)}
                    dx={-8}
                    width={50}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="reach"
                    stroke="#7c3aed"
                    strokeWidth={2.5}
                    fill="url(#gradReach)"
                    dot={false}
                    activeDot={{ r: 5, fill: "#7c3aed", stroke: "#fff", strokeWidth: 2 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="engagement"
                    stroke="#ec4899"
                    strokeWidth={2.5}
                    fill="url(#gradEng)"
                    dot={false}
                    activeDot={{ r: 5, fill: "#ec4899", stroke: "#fff", strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Two Column: Top Posts + AI Insights */}
        {/* ----------------------------------------------------------------- */}
        <div className="grid gap-6 lg:grid-cols-[1fr_0.65fr]">
          {/* Top Performing Posts */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>Top Posts</h2>
                <button
                  className="flex items-center gap-1 text-xs font-medium transition-colors"
                  style={{ color: "var(--accent-purple)" }}
                >
                  View All <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="space-y-1">
                {topPosts.map((post, idx) => {
                  const PlatformIcon = platformIconMap[post.platform] ?? Eye;
                  const pColor = platformColorMap[post.platform] ?? "#6B7280";
                  return (
                    <motion.div
                      key={post.id}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: 0.15 + idx * 0.06 }}
                      className="group flex items-start gap-3 rounded-xl p-3 -mx-1 transition-colors cursor-pointer"
                      style={{ ["--hover-bg" as string]: "var(--surface-bg-hover)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-bg-hover)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      {/* Platform icon with colored dot */}
                      <div
                        className="flex-shrink-0 w-12 h-12 rounded-lg flex items-center justify-center"
                        style={{
                          background: `${pColor}12`,
                          border: `1px solid ${pColor}25`,
                        }}
                      >
                        <PlatformIcon className="w-5 h-5" style={{ color: pColor }} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="platform" platform={post.platform} size="sm">
                            {post.platform.charAt(0).toUpperCase() + post.platform.slice(1)}
                          </Badge>
                          <span className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>
                            {formatDate(post.date)}
                          </span>
                        </div>
                        <p className="text-sm leading-relaxed line-clamp-2" style={{ color: "var(--page-text)" }}>
                          {post.content}
                        </p>
                        <div className="flex items-center gap-4 mt-2">
                          <span className="flex items-center gap-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                            <ThumbsUp className="w-3 h-3" />
                            {formatNumber(post.likes)}
                          </span>
                          <span className="flex items-center gap-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                            <MessageCircle className="w-3 h-3" />
                            {formatNumber(post.comments)}
                          </span>
                          <span className="flex items-center gap-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                            <Share2 className="w-3 h-3" />
                            {formatNumber(post.shares)}
                          </span>
                        </div>
                      </div>

                      <ArrowUpRight
                        className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1"
                        style={{ color: "var(--page-text-muted)" }}
                      />
                    </motion.div>
                  );
                })}
              </div>
            </Card>
          </motion.div>

          {/* AI Insights */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
          >
            <Card>
              <div className="flex items-center gap-2 mb-5">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center"
                  style={{
                    background: "linear-gradient(135deg, rgba(124,58,237,0.15), rgba(236,72,153,0.1))",
                    border: "1px solid rgba(124,58,237,0.2)",
                  }}
                >
                  <Brain className="w-4 h-4" style={{ color: "var(--accent-purple)" }} />
                </div>
                <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>AI Insights</h2>
              </div>

              <div className="space-y-3">
                {aiInsights.map((insight, idx) => {
                  const Icon = insight.icon;
                  return (
                    <motion.div
                      key={insight.id}
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: 0.2 + idx * 0.08 }}
                      className="rounded-xl p-3.5 transition-colors"
                      style={{
                        borderLeft: `3px solid ${insight.accentColor}`,
                        background: "var(--surface-bg-hover)",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = `${insight.accentColor}08`)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--surface-bg-hover)")}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                          style={{
                            background: `linear-gradient(135deg, ${insight.gradientFrom}18, ${insight.gradientTo}10)`,
                          }}
                        >
                          <Icon className="w-4 h-4" style={{ color: insight.accentColor }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium leading-snug" style={{ color: "var(--page-heading)" }}>
                            {insight.title}
                          </p>
                          <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--page-text-muted)" }}>
                            {insight.description}
                          </p>
                          <button
                            className="mt-2 text-[11px] font-semibold flex items-center gap-1 transition-opacity hover:opacity-80"
                            style={{ color: insight.accentColor }}
                          >
                            <Zap className="w-3 h-3" /> Apply This
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </Card>
          </motion.div>
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* Platform Breakdown + Engagement Pie */}
        {/* ----------------------------------------------------------------- */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Platform Breakdown */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <Card className="h-full">
              <h2 className="text-lg font-semibold mb-5" style={{ color: "var(--page-heading)" }}>
                Platform Breakdown
              </h2>

              <div className="space-y-5">
                {platformBreakdown.map((p, idx) => {
                  const Icon = p.icon;
                  return (
                    <motion.div
                      key={p.name}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: 0.25 + idx * 0.06 }}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2.5">
                          <div
                            className="w-8 h-8 rounded-lg flex items-center justify-center"
                            style={{
                              backgroundColor: `${p.color}15`,
                              border: `1px solid ${p.color}30`,
                            }}
                          >
                            <Icon className="w-4 h-4" style={{ color: p.color }} />
                          </div>
                          <span className="text-sm font-medium" style={{ color: "var(--page-text)" }}>
                            {p.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
                            {p.engagement}% eng
                          </span>
                          <span
                            className="text-[11px] font-semibold"
                            style={{ color: p.growth >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}
                          >
                            {p.growth >= 0 ? "+" : ""}{p.growth}%
                          </span>
                        </div>
                      </div>
                      {/* Horizontal bar */}
                      <div
                        className="h-2 rounded-full overflow-hidden"
                        style={{ background: "var(--surface-bg-hover)" }}
                      >
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${p.share}%` }}
                          transition={{ duration: 0.8, delay: 0.3 + idx * 0.08 }}
                          className="h-full rounded-full"
                          style={{
                            background: `linear-gradient(90deg, ${p.color}, ${p.color}99)`,
                          }}
                        />
                      </div>
                      <p className="text-[11px] mt-1" style={{ color: "var(--page-text-muted)" }}>
                        {formatNumber(p.reach)} reach
                      </p>
                    </motion.div>
                  );
                })}
              </div>
            </Card>
          </motion.div>

          {/* Engagement Distribution Pie */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
          >
            <Card className="h-full">
              <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--page-heading)" }}>
                Engagement Distribution
              </h2>
              <p className="text-sm mb-4" style={{ color: "var(--page-text-muted)" }}>
                Breakdown by interaction type
              </p>

              <div className="h-[220px] relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={engagementDistribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={65}
                      outerRadius={90}
                      dataKey="value"
                      stroke="none"
                      paddingAngle={3}
                    >
                      {engagementDistribution.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                {/* Center label */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="text-center">
                    <p className="text-xl font-bold" style={{ color: "var(--page-heading)" }}>
                      {formatNumber(totalEngagement)}
                    </p>
                    <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
                      Total
                    </p>
                  </div>
                </div>
              </div>

              {/* Legend */}
              <div className="grid grid-cols-2 gap-3 mt-4">
                {engagementDistribution.map((item) => (
                  <div key={item.name} className="flex items-center gap-2 text-xs">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: item.color }}
                    />
                    <span style={{ color: "var(--page-text-secondary)" }}>{item.name}</span>
                    <span className="ml-auto font-medium" style={{ color: "var(--page-text)" }}>
                      {formatNumber(item.value)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>
        </div>
      </div>
    </DashboardLayout>
  );
}
