import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  CalendarDays,
  Sparkles,
  Eye,
  Heart,
  Users,
  FileText,
  TrendingUp,
  ArrowRight,
  Lightbulb,
  RefreshCw,
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
import { useAuthStore } from "@/stores/authStore";
import api from "@/lib/api";
import { formatNumber } from "@/lib/utils";

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [topPosts, setTopPosts] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const accountId = localStorage.getItem("account_id");

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const firstName = user?.full_name?.split(" ")[0] ?? "there";

  useEffect(() => {
    if (!accountId) return;
    const load = async () => {
      try {
        setLoading(true);
        const [ovRes, trRes, tpRes, notifRes] = await Promise.allSettled([
          api.get(`/accounts/${accountId}/analytics/overview?period=7d`),
          api.get(`/accounts/${accountId}/analytics/trends?period=7d&group_by=day`),
          api.get(`/accounts/${accountId}/analytics/top-posts?period=30d&limit=5`),
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
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [accountId]);

  const stats = [
    {
      label: "Total Reach",
      value: overview ? formatNumber(overview.total_reach) : "—",
      change: overview?.comparison?.reach_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <Eye className="h-5 w-5" />,
    },
    {
      label: "Engagement",
      value: overview ? formatNumber(overview.total_engagement) : "—",
      change: overview?.comparison?.engagement_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <Heart className="h-5 w-5" />,
    },
    {
      label: "Posts Published",
      value: overview ? String(overview.total_posts) : "—",
      change: null,
      changeLabel: "this period",
      icon: <FileText className="h-5 w-5" />,
    },
    {
      label: "Avg Engagement Rate",
      value: overview ? `${(overview.avg_engagement_rate * 100).toFixed(2)}%` : "—",
      change: overview?.comparison?.engagement_rate_change_pct ?? null,
      changeLabel: "vs last week",
      icon: <TrendingUp className="h-5 w-5" />,
    },
  ];

  const chartData = trends.map((t) => ({
    day: new Date(t.date).toLocaleDateString("en-US", { weekday: "short" }),
    reach: t.reach,
    engagement: t.engagement,
  }));

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl">Welcome back, {firstName}! 👋</h1>
            <p className="mt-1 text-sm text-gray-400">{today}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/create-post")}>
              Create Post
            </Button>
            <Button size="sm" variant="secondary" icon={<CalendarDays className="h-4 w-4" />} onClick={() => navigate("/calendar")}>
              View Calendar
            </Button>
            <Button size="sm" variant="secondary" icon={<Sparkles className="h-4 w-4" />} onClick={() => navigate("/strategy")}>
              Generate Strategy
            </Button>
          </div>
        </div>

        {/* Stats row */}
        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-28 rounded-2xl bg-white/5 animate-pulse" />
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

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Performance chart */}
          <GlassCard className="lg:col-span-2">
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-purple-400" />
                <h3 className="text-base font-semibold text-white">Performance This Week</h3>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigate("/analytics")}>
                View Analytics
              </Button>
            </div>
            {loading ? (
              <div className="h-64 flex items-center justify-center">
                <RefreshCw className="h-6 w-6 text-purple-400 animate-spin" />
              </div>
            ) : chartData.length > 0 ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="reachGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="day" stroke="#6B7280" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#6B7280" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => formatNumber(v)} />
                    <Tooltip
                      contentStyle={{
                        background: "rgba(15,15,30,0.95)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "12px",
                        color: "#fff",
                      }}
                    />
                    <Area type="monotone" dataKey="reach" stroke="#a855f7" strokeWidth={2} fill="url(#reachGrad)" name="Reach" />
                    <Area type="monotone" dataKey="engagement" stroke="#3b82f6" strokeWidth={2} fill="url(#engGrad)" name="Engagement" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-sm gap-2">
                <TrendingUp className="h-8 w-8 opacity-30" />
                <p>No performance data yet — publish your first post!</p>
              </div>
            )}
          </GlassCard>

          {/* AI Insights / Notifications */}
          <GlassCard>
            <div className="mb-5 flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-amber-400" />
              <h3 className="text-base font-semibold text-white">Notifications</h3>
            </div>
            {loading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 rounded-xl bg-white/5 animate-pulse" />
                ))}
              </div>
            ) : notifications.length > 0 ? (
              <div className="space-y-3">
                {notifications.map((n: any, i: number) => (
                  <motion.div
                    key={n.id || i}
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="rounded-xl border border-white/5 bg-white/5 p-3"
                  >
                    <div className="mb-1.5">
                      <Badge
                        variant={n.type === "success" ? "success" : n.type === "warning" ? "warning" : "info"}
                        size="sm"
                      >
                        {n.type || "Info"}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-300">{n.message || n.title}</p>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500 text-sm gap-2">
                <Lightbulb className="h-8 w-8 opacity-30" />
                <p>No notifications yet</p>
              </div>
            )}
            <Button size="sm" variant="ghost" className="mt-4 w-full" onClick={() => navigate("/strategy")}>
              See full strategy <ArrowRight className="h-4 w-4" />
            </Button>
          </GlassCard>
        </div>

        {/* Top posts */}
        <GlassCard>
          <div className="mb-5 flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Top Performing Posts</h3>
            <Button size="sm" variant="ghost" onClick={() => navigate("/analytics")}>
              View all
            </Button>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-14 rounded-xl bg-white/5 animate-pulse" />
              ))}
            </div>
          ) : topPosts.length > 0 ? (
            <div className="space-y-2">
              {topPosts.map((post: any, i: number) => (
                <div
                  key={`${post.post_id}-${post.platform}-${i}`}
                  className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/5 p-3 transition-colors hover:bg-white/10"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-purple-600/20 to-blue-600/20 text-sm font-bold text-purple-400">
                    {i + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">{post.content}</p>
                    <p className="text-xs text-gray-500 capitalize">{post.platform}</p>
                  </div>
                  <div className="hidden text-right sm:block">
                    <p className="text-sm font-semibold text-emerald-400">
                      {post.engagement_rate != null ? `${(post.engagement_rate * 100).toFixed(1)}%` : "—"}
                    </p>
                    <p className="text-xs text-gray-500">engagement</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-white">{formatNumber(post.total_engagement)}</p>
                    <p className="text-xs text-gray-500">interactions</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-10 text-slate-500 text-sm gap-2">
              <FileText className="h-8 w-8 opacity-30" />
              <p>No published posts yet — create your first post!</p>
              <Button size="sm" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/create-post")}>
                Create Post
              </Button>
            </div>
          )}
        </GlassCard>
      </div>
    </DashboardLayout>
  );
}
