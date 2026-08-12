import { useState } from "react";
import { motion } from "framer-motion";
import {
  Shield,
  Users,
  Building2,
  CreditCard,
  DollarSign,
  FileText,
  Cpu,
  Activity,
  Database,
  AlertTriangle,
  Clock,
  UserCog,
  Settings,
  ChevronRight,
  ArrowUpRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { cn, formatNumber, formatDate, formatCurrency } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------
const userGrowthData = [
  { month: "Apr", users: 1240 },
  { month: "May", users: 1580 },
  { month: "Jun", users: 1910 },
  { month: "Jul", users: 2340 },
  { month: "Aug", users: 2780 },
  { month: "Sep", users: 3120 },
  { month: "Oct", users: 3690 },
  { month: "Nov", users: 4210 },
  { month: "Dec", users: 4530 },
  { month: "Jan", users: 5180 },
  { month: "Feb", users: 5740 },
  { month: "Mar", users: 6320 },
];

const revenueData = [
  { month: "Apr", starter: 4200, professional: 12800, enterprise: 28000 },
  { month: "May", starter: 4800, professional: 14200, enterprise: 30500 },
  { month: "Jun", starter: 5100, professional: 15600, enterprise: 31200 },
  { month: "Jul", starter: 5600, professional: 17400, enterprise: 34800 },
  { month: "Aug", starter: 6100, professional: 19200, enterprise: 37500 },
  { month: "Sep", starter: 6500, professional: 20800, enterprise: 39200 },
  { month: "Oct", starter: 7200, professional: 23100, enterprise: 42000 },
  { month: "Nov", starter: 7800, professional: 24800, enterprise: 44500 },
  { month: "Dec", starter: 8100, professional: 25600, enterprise: 45200 },
  { month: "Jan", starter: 8900, professional: 28200, enterprise: 48800 },
  { month: "Feb", starter: 9400, professional: 29800, enterprise: 51200 },
  { month: "Mar", starter: 10200, professional: 32400, enterprise: 54800 },
];

const recentSignups = [
  { name: "Sarah Chen", email: "sarah.chen@techstart.io", plan: "Professional", date: "2026-03-29", status: "active" },
  { name: "Marcus Williams", email: "marcus@growthlab.co", plan: "Enterprise", date: "2026-03-29", status: "active" },
  { name: "Priya Patel", email: "priya@contentforge.com", plan: "Starter", date: "2026-03-28", status: "trial" },
  { name: "James O'Brien", email: "james.obrien@adwave.io", plan: "Professional", date: "2026-03-28", status: "active" },
  { name: "Aisha Mohammed", email: "aisha@brandpulse.co", plan: "Starter", date: "2026-03-27", status: "trial" },
  { name: "David Kim", email: "david.kim@nexusdigital.io", plan: "Enterprise", date: "2026-03-27", status: "active" },
  { name: "Emma Rodriguez", email: "emma@socialcraft.co", plan: "Professional", date: "2026-03-26", status: "active" },
  { name: "Liam Thompson", email: "liam@pixelreach.com", plan: "Starter", date: "2026-03-26", status: "trial" },
  { name: "Sofia Nakamura", email: "sofia@zenithcm.io", plan: "Professional", date: "2026-03-25", status: "active" },
  { name: "Oliver Becker", email: "oliver@marketedge.de", plan: "Enterprise", date: "2026-03-25", status: "active" },
];

const systemHealth = [
  { label: "API Response Time", value: "42ms", status: "good", icon: Clock },
  { label: "Database Connections", value: "127 / 500", status: "good", icon: Database },
  { label: "Queue Size", value: "2,841", status: "warning", icon: Activity },
  { label: "Error Rate", value: "0.03%", status: "good", icon: AlertTriangle },
];

// ---------------------------------------------------------------------------
// Custom chart tooltip
// ---------------------------------------------------------------------------
function ChartTooltip({ active, payload, label }: any) {
  const isDark = useUIStore((s) => s.theme) === "dark";
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl backdrop-blur-xl px-4 py-3 shadow-xl"
      style={{
        backgroundColor: isDark ? "rgba(18,18,28,0.96)" : "rgba(255,255,255,0.98)",
        border: `1px solid ${isDark ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.08)"}`,
      }}
    >
      <p className="text-xs mb-2" style={{ color: "var(--page-text-secondary)" }}>{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === "number" && entry.value > 100 ? formatCurrency(entry.value) : formatNumber(entry.value)}
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AdminDashboard() {
  const [, setImpersonateOpen] = useState(false);
  const isDark = useUIStore((s) => s.theme) === "dark";

  const planBadgeVariant = (plan: string) => {
    if (plan === "Enterprise") return "warning";
    if (plan === "Professional") return "info";
    return "default";
  };

  const statusBadgeVariant = (status: string) => {
    if (status === "active") return "success";
    if (status === "trial") return "info";
    return "danger";
  };

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-8"
      >
        {/* ----------------------------------------------------------------- */}
        {/* Header                                                            */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-red-600/20 to-orange-600/20 border border-red-500/20 flex items-center justify-center">
              <Shield className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--page-heading)" }}>Admin Panel</h1>
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>System overview & management</p>
            </div>
          </div>

          <Badge variant="success" dot>
            System Status: Operational
          </Badge>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Stats Row                                                         */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <StatCard label="Total Users" value={formatNumber(6320)} change={10.1} changeLabel="vs last month" icon={<Users className="w-5 h-5" />} />
          <StatCard label="Total Accounts" value={formatNumber(1840)} change={8.4} changeLabel="vs last month" icon={<Building2 className="w-5 h-5" />} />
          <StatCard label="Active Subscriptions" value={formatNumber(1520)} change={12.3} changeLabel="vs last month" icon={<CreditCard className="w-5 h-5" />} />
          <StatCard label="Monthly Revenue" value="$97.4K" change={14.2} changeLabel="vs last month" icon={<DollarSign className="w-5 h-5" />} />
          <StatCard label="Posts Published" value={formatNumber(24680)} change={18.7} changeLabel="this month" icon={<FileText className="w-5 h-5" />} />
          <StatCard label="AI API Costs" value="$4.2K" change={-6.1} changeLabel="vs last month" icon={<Cpu className="w-5 h-5" />} />
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Charts Row                                                        */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* User Growth Chart */}
          <GlassCard>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>User Growth</h3>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>Last 12 months</p>
              </div>
              <Badge variant="success" dot>
                +{formatNumber(5080)} YTD
              </Badge>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={userGrowthData}>
                  <defs>
                    <linearGradient id="userGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)"} />
                  <XAxis dataKey="month" tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="users" name="Users" stroke="#7c3aed" fill="url(#userGrad)" strokeWidth={2.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>

          {/* Revenue Chart */}
          <GlassCard>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>Revenue by Plan</h3>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>Last 12 months</p>
              </div>
              <Badge variant="success" dot>
                +22% MoM
              </Badge>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={revenueData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)"} />
                  <XAxis dataKey="month" tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 12 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: 12, color: isDark ? "#94a3b8" : "#64748b" }}
                    iconType="circle"
                    iconSize={8}
                  />
                  <Bar dataKey="starter" name="Starter" stackId="a" fill="#38bdf8" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="professional" name="Professional" stackId="a" fill="#7c3aed" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="enterprise" name="Enterprise" stackId="a" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Recent Signups Table                                              */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>Recent Signups</h3>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>Latest user registrations</p>
              </div>
              <Button variant="ghost" size="sm" icon={<ArrowUpRight className="w-4 h-4" />} iconPosition="right">
                View All
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                    <th className="text-left font-medium pb-3 pl-2" style={{ color: "var(--page-text-muted)" }}>Name</th>
                    <th className="text-left font-medium pb-3" style={{ color: "var(--page-text-muted)" }}>Email</th>
                    <th className="text-left font-medium pb-3" style={{ color: "var(--page-text-muted)" }}>Plan</th>
                    <th className="text-left font-medium pb-3" style={{ color: "var(--page-text-muted)" }}>Signup Date</th>
                    <th className="text-left font-medium pb-3" style={{ color: "var(--page-text-muted)" }}>Status</th>
                    <th className="text-right font-medium pb-3 pr-2" style={{ color: "var(--page-text-muted)" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentSignups.map((user, i) => (
                    <tr key={i} className="last:border-0 hover:bg-[var(--sidebar-hover-bg)] transition-colors" style={{ borderBottom: "1px solid var(--surface-border)" }}>
                      <td className="py-3 pl-2">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center text-xs font-semibold text-purple-300">
                            {user.name.split(" ").map((n) => n[0]).join("")}
                          </div>
                          <span className="font-medium" style={{ color: "var(--page-heading)" }}>{user.name}</span>
                        </div>
                      </td>
                      <td className="py-3" style={{ color: "var(--page-text-secondary)" }}>{user.email}</td>
                      <td className="py-3">
                        <Badge variant={planBadgeVariant(user.plan)} size="sm">{user.plan}</Badge>
                      </td>
                      <td className="py-3 tabular-nums" style={{ color: "var(--page-text-secondary)" }}>{formatDate(user.date)}</td>
                      <td className="py-3">
                        <Badge variant={statusBadgeVariant(user.status)} dot size="sm">
                          {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3 pr-2 text-right">
                        <Button variant="ghost" size="sm" icon={<ChevronRight className="w-3.5 h-3.5" />}>
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* System Health + Quick Actions                                     */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* System Health */}
          <div className="lg:col-span-2">
            <GlassCard>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>System Health</h3>
                  <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>Real-time infrastructure metrics</p>
                </div>
                <Badge variant="success" dot>All Systems Go</Badge>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {systemHealth.map((metric) => {
                  const Icon = metric.icon;
                  const isWarning = metric.status === "warning";
                  return (
                    <div
                      key={metric.label}
                      className={cn(
                        "rounded-xl border p-4 transition-colors",
                        isWarning ? "bg-amber-500/5 border-amber-500/20" : ""
                      )}
                      style={!isWarning ? { backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" } : undefined}
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <Icon className={cn("w-4 h-4", isWarning ? "text-amber-400" : "text-emerald-400")} />
                        <span className="text-xs font-medium" style={{ color: "var(--page-text-secondary)" }}>{metric.label}</span>
                      </div>
                      <p className={cn("text-xl font-bold tabular-nums", isWarning ? "text-amber-300" : "")} style={!isWarning ? { color: "var(--page-heading)" } : undefined}>
                        {metric.value}
                      </p>
                      <div className="mt-2 flex items-center gap-1.5">
                        <span className={cn("w-1.5 h-1.5 rounded-full", isWarning ? "bg-amber-400" : "bg-emerald-400")} />
                        <span className={cn("text-[11px] font-medium", isWarning ? "text-amber-400" : "text-emerald-400")}>
                          {isWarning ? "Elevated" : "Normal"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          </div>

          {/* Quick Actions */}
          <GlassCard>
            <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--page-heading)" }}>Quick Actions</h3>
            <p className="text-sm mb-6" style={{ color: "var(--page-text-secondary)" }}>Administrative operations</p>

            <div className="space-y-3">
              <button
                onClick={() => setImpersonateOpen(true)}
                className="w-full flex items-center gap-3 rounded-xl bg-amber-500/5 border border-amber-500/20 hover:bg-amber-500/10 transition-colors p-4 text-left group cursor-pointer"
              >
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center group-hover:bg-amber-500/20 transition-colors">
                  <UserCog className="w-5 h-5 text-amber-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>Impersonate User</p>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>View the app as another user</p>
                </div>
                <ChevronRight className="w-4 h-4 text-[var(--page-text-muted)] group-hover:text-amber-400 transition-colors" />
              </button>

              <button className="w-full flex items-center gap-3 rounded-xl bg-[var(--sidebar-hover-bg)] border border-[var(--surface-border)] hover:bg-[var(--sidebar-hover-bg)] transition-colors p-4 text-left group cursor-pointer">
                <div className="w-10 h-10 rounded-xl bg-[var(--sidebar-hover-bg)] border border-[var(--surface-border)] flex items-center justify-center transition-colors">
                  <Settings className="w-5 h-5" style={{ color: "var(--page-text-secondary)" }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>System Settings</p>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>Manage global configuration</p>
                </div>
                <ChevronRight className="w-4 h-4 text-[var(--page-text-muted)] group-hover:text-[var(--page-heading)] transition-colors" />
              </button>

              <button className="w-full flex items-center gap-3 rounded-xl bg-[var(--sidebar-hover-bg)] border border-[var(--surface-border)] hover:bg-[var(--sidebar-hover-bg)] transition-colors p-4 text-left group cursor-pointer">
                <div className="w-10 h-10 rounded-xl bg-[var(--sidebar-hover-bg)] border border-[var(--surface-border)] flex items-center justify-center transition-colors">
                  <Database className="w-5 h-5" style={{ color: "var(--page-text-secondary)" }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>Database Console</p>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>Run queries & view metrics</p>
                </div>
                <ChevronRight className="w-4 h-4 text-[var(--page-text-muted)] group-hover:text-[var(--page-heading)] transition-colors" />
              </button>
            </div>
          </GlassCard>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
