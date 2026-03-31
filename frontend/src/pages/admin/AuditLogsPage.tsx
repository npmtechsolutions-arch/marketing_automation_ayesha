import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScrollText,
  Search,
  ChevronDown,
  ChevronRight,
  Download,
  Calendar,
  Globe,
  Clock,
  User,
  LogIn,
  FilePlus,
  Trash2,
  Link2,
  CreditCard,
  Settings,
  Copy,
  Check,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.04, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ---------------------------------------------------------------------------
// Action type config
// ---------------------------------------------------------------------------
const actionConfig: Record<string, { label: string; color: string; bg: string; border: string; icon: typeof LogIn }> = {
  "user.login": { label: "Login", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20", icon: LogIn },
  "user.logout": { label: "Logout", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20", icon: LogIn },
  "post.create": { label: "Post Created", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: FilePlus },
  "post.delete": { label: "Post Deleted", color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", icon: Trash2 },
  "post.update": { label: "Post Updated", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: FilePlus },
  "platform.connect": { label: "Platform Connected", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20", icon: Link2 },
  "platform.disconnect": { label: "Platform Disconnected", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20", icon: Link2 },
  "billing.upgrade": { label: "Plan Upgraded", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", icon: CreditCard },
  "billing.downgrade": { label: "Plan Downgraded", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", icon: CreditCard },
  "settings.update": { label: "Settings Updated", color: "text-gray-400", bg: "bg-white/5", border: "border-white/10", icon: Settings },
};

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------
const mockLogs = [
  {
    id: 1, timestamp: "2026-03-30T09:42:18Z", user: "Sarah Chen", action: "user.login", resource: "Session #84921", ip: "104.28.12.91",
    details: { user_agent: "Chrome 124 / macOS", mfa_used: true },
  },
  {
    id: 2, timestamp: "2026-03-30T09:38:05Z", user: "Marcus Williams", action: "post.create", resource: "Post #12847", ip: "72.14.201.18",
    details: { title: "Q1 Social Media Recap", platforms: ["instagram", "linkedin"], scheduled_for: "2026-04-01T10:00:00Z" },
  },
  {
    id: 3, timestamp: "2026-03-30T09:31:44Z", user: "Priya Patel", action: "platform.connect", resource: "Instagram @contentforge", ip: "49.36.128.77",
    details: { platform: "instagram", account_type: "business", followers: 24500 },
  },
  {
    id: 4, timestamp: "2026-03-30T09:24:11Z", user: "James O'Brien", action: "billing.upgrade", resource: "Subscription #4821", ip: "86.45.112.30",
    details: {
      old_values: { plan: "Starter", price: 29 },
      new_values: { plan: "Professional", price: 79 },
    },
  },
  {
    id: 5, timestamp: "2026-03-30T09:18:33Z", user: "David Kim", action: "post.delete", resource: "Post #12790", ip: "211.48.76.22",
    details: { title: "Draft: TikTok Strategy", reason: "Outdated content" },
  },
  {
    id: 6, timestamp: "2026-03-30T09:12:07Z", user: "Emma Rodriguez", action: "settings.update", resource: "Team Settings", ip: "189.203.44.18",
    details: {
      old_values: { default_approval: false, timezone: "America/New_York" },
      new_values: { default_approval: true, timezone: "America/Chicago" },
    },
  },
  {
    id: 7, timestamp: "2026-03-30T08:55:22Z", user: "Liam Thompson", action: "user.login", resource: "Session #84918", ip: "82.132.240.15",
    details: { user_agent: "Safari 19 / iOS 20", mfa_used: false },
  },
  {
    id: 8, timestamp: "2026-03-30T08:47:51Z", user: "Sofia Nakamura", action: "post.create", resource: "Post #12845", ip: "126.75.112.40",
    details: { title: "Spring Campaign Launch", platforms: ["facebook", "twitter", "linkedin"], ai_generated: true },
  },
  {
    id: 9, timestamp: "2026-03-30T08:34:19Z", user: "Oliver Becker", action: "platform.disconnect", resource: "Twitter @marketedge_de", ip: "91.64.22.178",
    details: { platform: "twitter", reason: "Account migration" },
  },
  {
    id: 10, timestamp: "2026-03-30T08:21:08Z", user: "Aisha Mohammed", action: "post.create", resource: "Post #12842", ip: "41.58.190.22",
    details: { title: "Brand Awareness Tips", platforms: ["instagram"], ai_generated: true },
  },
  {
    id: 11, timestamp: "2026-03-30T08:10:44Z", user: "Sarah Chen", action: "settings.update", resource: "Notification Preferences", ip: "104.28.12.91",
    details: {
      old_values: { email_digest: "daily", push_enabled: true },
      new_values: { email_digest: "weekly", push_enabled: true },
    },
  },
  {
    id: 12, timestamp: "2026-03-30T07:58:31Z", user: "Marcus Williams", action: "billing.upgrade", resource: "Subscription #4780", ip: "72.14.201.18",
    details: {
      old_values: { plan: "Professional", price: 79 },
      new_values: { plan: "Enterprise", price: 199 },
    },
  },
  {
    id: 13, timestamp: "2026-03-30T07:45:17Z", user: "Mia Chang", action: "post.update", resource: "Post #12830", ip: "116.228.64.55",
    details: { title: "Updated: Weekly Newsletter", changes: ["content", "schedule", "platforms"] },
  },
  {
    id: 14, timestamp: "2026-03-30T07:32:05Z", user: "David Kim", action: "platform.connect", resource: "LinkedIn Company Page", ip: "211.48.76.22",
    details: { platform: "linkedin", account_type: "company", followers: 8200 },
  },
  {
    id: 15, timestamp: "2026-03-30T07:18:42Z", user: "Ethan Murphy", action: "user.login", resource: "Session #84912", ip: "98.24.181.55",
    details: { user_agent: "Firefox 130 / Windows 11", mfa_used: true },
  },
  {
    id: 16, timestamp: "2026-03-30T07:05:28Z", user: "Isabella Torres", action: "post.create", resource: "Post #12828", ip: "201.162.88.14",
    details: { title: "Producto Highlight: March", platforms: ["instagram", "facebook"], ai_generated: false },
  },
  {
    id: 17, timestamp: "2026-03-30T06:52:14Z", user: "Noah Johnson", action: "user.login", resource: "Session #84908", ip: "73.162.44.200",
    details: { user_agent: "Chrome 124 / Windows 11", mfa_used: false },
  },
  {
    id: 18, timestamp: "2026-03-30T06:38:55Z", user: "Ava Martinez", action: "settings.update", resource: "Brand Kit", ip: "67.180.112.88",
    details: {
      old_values: { primary_color: "#6B21A8", font: "Inter" },
      new_values: { primary_color: "#7C3AED", font: "Plus Jakarta Sans" },
    },
  },
  {
    id: 19, timestamp: "2026-03-30T06:25:39Z", user: "Priya Patel", action: "post.delete", resource: "Post #12815", ip: "49.36.128.77",
    details: { title: "Test Post", reason: "Accidental creation" },
  },
  {
    id: 20, timestamp: "2026-03-30T06:12:01Z", user: "Oliver Becker", action: "billing.downgrade", resource: "Subscription #4710", ip: "91.64.22.178",
    details: {
      old_values: { plan: "Enterprise", seats: 10 },
      new_values: { plan: "Enterprise", seats: 6 },
    },
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState("all");
  const [userFilter, setUserFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const uniqueActions = [...new Set(mockLogs.map((l) => l.action))];

  const filtered = mockLogs.filter((log) => {
    const matchesAction = actionFilter === "all" || log.action === actionFilter;
    const matchesUser = userFilter === "" || log.user.toLowerCase().includes(userFilter.toLowerCase());
    return matchesAction && matchesUser;
  });

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  };

  const copyJson = (id: number, data: any) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-600/20 to-blue-600/20 border border-cyan-500/20 flex items-center justify-center">
              <ScrollText className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Audit Logs</h1>
              <p className="text-sm text-gray-400">Track all system activity</p>
            </div>
          </div>

          <Button variant="secondary" size="sm" icon={<Download className="w-4 h-4" />}>
            Export CSV
          </Button>
        </motion.div>

        {/* Filters */}
        <motion.div variants={fadeUp} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 max-w-xs">
            <Input
              placeholder="Filter by user..."
              icon={<Search className="w-4 h-4" />}
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
            />
          </div>

          <div className="relative">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="appearance-none bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 pr-10 text-sm text-white outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all cursor-pointer"
            >
              <option value="all" className="bg-slate-900">All Actions</option>
              {uniqueActions.map((a) => (
                <option key={a} value={a} className="bg-slate-900">
                  {actionConfig[a]?.label ?? a}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>

          <div className="flex items-center gap-2 bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-2.5 text-sm text-gray-400">
            <Calendar className="w-4 h-4" />
            <span>Mar 30, 2026</span>
          </div>
        </motion.div>

        {/* Log Entries */}
        <motion.div variants={fadeUp} className="space-y-2">
          {filtered.map((log) => {
            const config = actionConfig[log.action] ?? {
              label: log.action, color: "text-gray-400", bg: "bg-white/5", border: "border-white/10", icon: Settings,
            };
            const Icon = config.icon;
            const isExpanded = expandedId === log.id;

            return (
              <GlassCard key={log.id} padding="sm" className="!p-0">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : log.id)}
                  className="w-full flex items-center gap-4 p-4 text-left"
                >
                  {/* Timestamp */}
                  <div className="hidden sm:flex flex-col items-center min-w-[70px]">
                    <span className="text-xs font-mono text-gray-500">{formatTime(log.timestamp)}</span>
                  </div>

                  {/* User avatar */}
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center text-[10px] font-semibold text-purple-300 flex-shrink-0">
                    {log.user.split(" ").map((n) => n[0]).join("")}
                  </div>

                  {/* User + action */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-white">{log.user}</span>
                      <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border", config.bg, config.color, config.border)}>
                        <Icon className="w-3 h-3" />
                        {config.label}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 truncate">{log.resource}</p>
                  </div>

                  {/* IP */}
                  <div className="hidden md:flex items-center gap-1.5 text-xs text-gray-500 min-w-[120px]">
                    <Globe className="w-3 h-3" />
                    {log.ip}
                  </div>

                  {/* Expand indicator */}
                  <ChevronRight className={cn("w-4 h-4 text-gray-500 transition-transform duration-200 flex-shrink-0", isExpanded && "rotate-90")} />
                </button>

                {/* Expanded detail */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 pt-0">
                        <div className="rounded-xl bg-black/30 border border-white/5 p-4">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-medium text-gray-400">Event Details</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); copyJson(log.id, log.details); }}
                              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-white transition-colors"
                            >
                              {copiedId === log.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                              {copiedId === log.id ? "Copied" : "Copy"}
                            </button>
                          </div>
                          <pre className="text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        </div>

                        {/* Metadata row */}
                        <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-gray-500">
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(log.timestamp).toLocaleString()}</span>
                          <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> {log.ip}</span>
                          <span className="flex items-center gap-1"><User className="w-3 h-3" /> {log.user}</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </GlassCard>
            );
          })}
        </motion.div>

        {/* Results count */}
        <motion.div variants={fadeUp} className="text-center">
          <p className="text-sm text-gray-500">
            Showing {filtered.length} of {mockLogs.length} log entries
          </p>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
