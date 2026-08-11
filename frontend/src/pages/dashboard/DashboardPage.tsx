import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  CalendarDays,
  Sparkles,
  Eye,
  Heart,
  FileText,
  TrendingUp,
  ArrowRight,
  Bell,
  Trophy,
  Share2,
  Zap,
  ArrowUpRight,
  Clock,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { motion } from "framer-motion";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/Button";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import api, { getAccountId } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.04 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const theme = useUIStore((s) => s.theme);

  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [topPosts, setTopPosts] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const firstName = user?.full_name?.split(" ")[0] ?? "there";

  useEffect(() => {
    const load = async () => {
      const activeAccountId = await getAccountId();
      if (!activeAccountId) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const [ovRes, trRes, tpRes, notifRes] = await Promise.allSettled([
          api.get(`/accounts/${activeAccountId}/analytics/overview?period=7d`),
          api.get(`/accounts/${activeAccountId}/analytics/trends?period=7d&group_by=day`),
          api.get(`/accounts/${activeAccountId}/analytics/top-posts?period=30d&limit=5`),
          api.get(`/notifications/?limit=3`),
        ]);

        if (ovRes.status === "fulfilled") setOverview((ovRes.value as any).data);
        if (trRes.status === "fulfilled") {
          const data = (trRes.value as any).data;
          setTrends(Array.isArray(data) ? data : []);
        }
        if (tpRes.status === "fulfilled") {
          const data = (tpRes.value as any).data;
          setTopPosts(Array.isArray(data) ? data : []);
        }
        if (notifRes.status === "fulfilled") {
          const data = (notifRes.value as any).data;
          const items = data?.items || data || [];
          setNotifications(Array.isArray(items) ? items.slice(0, 3) : []);
        }
      } catch (e) {
        console.error("Dashboard data load error:", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const stats = [
    {
      label: "Total Reach",
      value: overview?.total_reach != null ? formatNumber(overview.total_reach) : "0",
      change: overview?.comparison?.reach_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <Eye className="h-5 w-5" />,
    },
    {
      label: "Total Engagement",
      value: overview?.total_engagement != null ? formatNumber(overview.total_engagement) : "0",
      change: overview?.comparison?.engagement_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <Heart className="h-5 w-5" />,
    },
    {
      label: "Posts Published",
      value: overview?.total_posts != null ? String(overview.total_posts) : "0",
      change: null,
      changeLabel: "this period",
      icon: <FileText className="h-5 w-5" />,
    },
    {
      label: "Avg Engagement Rate",
      value: overview?.avg_engagement_rate != null ? `${((overview.avg_engagement_rate || 0) * 100).toFixed(2)}%` : "0%",
      change: overview?.comparison?.engagement_rate_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <TrendingUp className="h-5 w-5" />,
    },
  ];

  const chartData = (Array.isArray(trends) ? trends : []).map((t) => ({
    day: t?.date ? new Date(t.date).toLocaleDateString("en-US", { weekday: "short" }) : "—",
    reach: t?.reach || 0,
    engagement: t?.engagement || 0,
  }));

  const isDark = theme === "dark";
  const chart = {
    reach: "#7c3aed",
    engagement: "#38bdf8",
    grid: isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)",
    axis: isDark ? "#94a3b8" : "#64748b",
    tooltipBg: isDark ? "rgba(18,18,28,0.96)" : "rgba(255,255,255,0.98)",
    tooltipBorder: isDark ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.08)",
    tooltipText: isDark ? "#f8fafc" : "#0f172a",
    tooltipShadow: isDark ? "0 16px 36px rgba(0,0,0,0.6)" : "0 12px 32px rgba(16,24,40,0.12)",
  };

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
        <p className="mb-2 text-xs font-bold" style={{ color: chart.tooltipText }}>{label}</p>
        <div className="space-y-1">
          {payload.map((p: any) => (
            <div key={p.name} className="flex items-center gap-2.5 text-xs font-medium" style={{ color: chart.tooltipText }}>
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
              <span style={{ opacity: 0.75 }}>{p.name}:</span>
              <span className="ml-auto font-bold tabular-nums">{formatNumber(p.value)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <DashboardLayout>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6 pb-12"
      >
        {/* Header Hero Bar */}
        <motion.div
          variants={itemVariants}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl" style={{ color: "var(--page-heading)" }}>
                Welcome back,{" "}
                <span
                  style={{
                    background: "linear-gradient(135deg, #7c3aed, #6366f1, #38bdf8)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  {firstName}
                </span>
              </h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/10 px-2.5 py-0.5 text-xs font-semibold text-purple-400 border border-purple-500/20">
                <Sparkles className="h-3 w-3" /> AI Active
              </span>
            </div>
            <p className="mt-1 text-sm font-medium" style={{ color: "var(--page-text-secondary)" }}>
              {today} • Your social channels are performing 14% above baseline
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              size="sm"
              variant="primary"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => navigate("/create-post")}
            >
              Create Post
            </Button>
            <Button
              size="sm"
              variant="secondary"
              icon={<CalendarDays className="h-4 w-4" />}
              onClick={() => navigate("/calendar")}
            >
              Calendar
            </Button>
            <Button
              size="sm"
              variant="secondary"
              icon={<Sparkles className="h-4 w-4" />}
              onClick={() => navigate("/strategy")}
            >
              AI Strategy
            </Button>
          </div>
        </motion.div>

        {/* Stats Row */}
        <motion.div variants={itemVariants}>
          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[...Array(4)].map((_, i) => (
                <StatCard key={i} label="" value="" loading />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {stats.map((s) => (
                <StatCard
                  key={s.label}
                  label={s.label}
                  value={s.value}
                  change={s.change}
                  changeLabel={s.changeLabel}
                  icon={s.icon}
                />
              ))}
            </div>
          )}
        </motion.div>

        {/* Main Charts & Side Panels */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Performance Chart */}
          <motion.div variants={itemVariants} className="lg:col-span-2">
            <GlassCard>
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-xl"
                    style={{
                      backgroundColor: "rgba(124,58,237,0.12)",
                      border: "1px solid rgba(124,58,237,0.22)",
                      color: "var(--accent-purple)",
                    }}
                  >
                    <TrendingUp className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold" style={{ color: "var(--page-heading)" }}>
                      Performance Velocity
                    </h3>
                    <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                      Reach vs Engagement (Last 7 Days)
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<ArrowUpRight className="h-4 w-4" />}
                  iconPosition="right"
                  onClick={() => navigate("/analytics")}
                >
                  Full Report
                </Button>
              </div>

              {/* Legend */}
              {!loading && chartData.length > 0 && (
                <div className="mb-4 mt-2 flex items-center gap-5">
                  <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--page-text-secondary)" }}>
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chart.reach }} /> Reach
                  </span>
                  <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--page-text-secondary)" }}>
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chart.engagement }} /> Engagement
                  </span>
                </div>
              )}

              {loading ? (
                <Skeleton variant="rect" height="260px" className="mt-2 !rounded-2xl" />
              ) : chartData.length > 0 ? (
                <div className="h-68 w-full" role="img" aria-label="Reach and engagement chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="reachGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={chart.reach} stopOpacity={0.45} />
                          <stop offset="95%" stopColor={chart.reach} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={chart.engagement} stopOpacity={0.40} />
                          <stop offset="95%" stopColor={chart.engagement} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                      <XAxis dataKey="day" stroke={chart.axis} fontSize={12} tickLine={false} axisLine={false} dy={6} />
                      <YAxis stroke={chart.axis} fontSize={12} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => formatNumber(v)} />
                      <Tooltip content={<ChartTooltip />} cursor={{ stroke: chart.grid, strokeWidth: 1.5 }} />
                      <Area type="monotone" dataKey="reach" stroke={chart.reach} strokeWidth={3} fill="url(#reachGrad)" name="Reach" activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }} />
                      <Area type="monotone" dataKey="engagement" stroke={chart.engagement} strokeWidth={3} fill="url(#engGrad)" name="Engagement" activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex h-64 flex-col items-center justify-center gap-2.5 text-sm" style={{ color: "var(--page-text-muted)" }}>
                  <TrendingUp className="h-10 w-10 opacity-30" />
                  <p className="font-medium">No performance trends recorded yet</p>
                  <Button size="sm" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/create-post")}>
                    Publish First Post
                  </Button>
                </div>
              )}
            </GlassCard>
          </motion.div>

          {/* Quick AI & Notifications Feed */}
          <motion.div variants={itemVariants} className="space-y-6">
            {/* AI Strategy Quick Widget */}
            <div
              className="rounded-2xl p-5 border relative overflow-hidden transition-all duration-300 hover:shadow-lg"
              style={{
                background: "linear-gradient(135deg, rgba(124,58,237,0.12), rgba(99,102,241,0.08))",
                borderColor: "rgba(124,58,237,0.25)",
              }}
            >
              <div className="flex items-center gap-2.5 mb-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 text-purple-400">
                  <Zap className="h-4 w-4" />
                </div>
                <h4 className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>AI Strategic Advisor</h4>
              </div>
              <p className="text-xs font-medium leading-relaxed mb-3.5" style={{ color: "var(--page-text-secondary)" }}>
                Optimal posting window for LinkedIn & Instagram today is <strong>4:30 PM – 6:00 PM</strong>.
              </p>
              <button
                onClick={() => navigate("/strategy")}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-purple-400 hover:text-purple-300 transition-colors cursor-pointer"
              >
                View Recommendations <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Notifications Card */}
            <GlassCard>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-lg"
                    style={{ backgroundColor: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.22)", color: "#f59e0b" }}
                  >
                    <Bell className="h-4 w-4" />
                  </div>
                  <h3 className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>Activity Feed</h3>
                </div>
                <Button size="sm" variant="ghost" onClick={() => navigate("/notifications")}>
                  View all
                </Button>
              </div>

              {loading ? (
                <div className="space-y-2.5">
                  {[...Array(3)].map((_, i) => (
                    <Skeleton key={i} variant="rect" height="52px" className="!rounded-xl" />
                  ))}
                </div>
              ) : notifications.length > 0 ? (
                <div className="space-y-2.5">
                  {notifications.map((n: any, i: number) => (
                    <div
                      key={n.id || i}
                      className="rounded-xl p-3 border transition-colors"
                      style={{
                        backgroundColor: "var(--sidebar-hover-bg)",
                        borderColor: "var(--surface-border)",
                      }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Badge
                          variant={n.type === "success" ? "success" : n.type === "warning" ? "warning" : "info"}
                          size="sm"
                        >
                          {n.type || "Update"}
                        </Badge>
                        <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>Just now</span>
                      </div>
                      <p className="text-xs font-medium leading-normal" style={{ color: "var(--page-text)" }}>
                        {n.message || n.title}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center gap-2 py-6 text-xs" style={{ color: "var(--page-text-muted)" }}>
                  <Bell className="h-6 w-6 opacity-30" />
                  <p>All caught up! No unread notifications.</p>
                </div>
              )}
            </GlassCard>
          </motion.div>
        </div>

        {/* Top Performing Posts Leaderboard */}
        <motion.div variants={itemVariants}>
          <GlassCard>
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{
                    backgroundColor: "rgba(16,185,129,0.12)",
                    border: "1px solid rgba(16,185,129,0.22)",
                    color: "#10b981",
                  }}
                >
                  <Trophy className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold" style={{ color: "var(--page-heading)" }}>
                    Top Performing Content
                  </h3>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                    Ranked by total engagement & reach across platforms
                  </p>
                </div>
              </div>
              <Button size="sm" variant="ghost" icon={<ArrowUpRight className="h-4 w-4" />} iconPosition="right" onClick={() => navigate("/analytics")}>
                Analytics Deep Dive
              </Button>
            </div>

            {loading ? (
              <div className="space-y-2.5">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} variant="rect" height="60px" className="!rounded-xl" />
                ))}
              </div>
            ) : topPosts.length > 0 ? (
              <div className="space-y-2.5">
                {topPosts.map((post: any, i: number) => (
                  <div
                    key={`${post.post_id}-${post.platform}-${i}`}
                    className="group flex items-center gap-4 rounded-xl p-3.5 border transition-all duration-200 hover:scale-[1.005] hover:shadow-sm"
                    style={{
                      backgroundColor: "var(--sidebar-hover-bg)",
                      borderColor: "var(--surface-border)",
                    }}
                  >
                    <div
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-extrabold tabular-nums shadow-xs"
                      style={{
                        backgroundColor: i === 0 ? "rgba(245,158,11,0.15)" : i === 1 ? "rgba(124,58,237,0.12)" : "rgba(100,116,139,0.12)",
                        color: i === 0 ? "#f59e0b" : i === 1 ? "#7c3aed" : "var(--page-text-secondary)",
                        border: `1px solid ${i === 0 ? "rgba(245,158,11,0.3)" : "var(--surface-border)"}`,
                      }}
                    >
                      #{i + 1}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold" style={{ color: "var(--page-text)" }}>
                        {post.content}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400">
                          {post.platform}
                        </span>
                        <span className="text-gray-400">•</span>
                        <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                          Published recently
                        </span>
                      </div>
                    </div>

                    <div className="hidden text-right sm:block">
                      <p className="text-sm font-bold text-emerald-500 tabular-nums">
                        {post.engagement_rate != null ? `${(post.engagement_rate * 100).toFixed(1)}%` : "—"}
                      </p>
                      <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>
                        Engagement Rate
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-sm font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>
                        {formatNumber(post.total_engagement)}
                      </p>
                      <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>
                        Interactions
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 py-12 text-sm" style={{ color: "var(--page-text-muted)" }}>
                <FileText className="h-10 w-10 opacity-30" />
                <p className="font-medium">No published post data available yet.</p>
                <Button size="sm" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/create-post")}>
                  Create First Post
                </Button>
              </div>
            )}
          </GlassCard>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
