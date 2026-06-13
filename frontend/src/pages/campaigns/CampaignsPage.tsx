import { useState } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Megaphone,
  DollarSign,
  TrendingUp,
  Target,
  Pause,
  Play,
  Edit3,
  Eye,
  BarChart3,
  Calendar,
} from "lucide-react";
import { Instagram, Linkedin, Twitter, Facebook, Youtube } from "@/components/shared/SocialIcons";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { cn, formatNumber, formatDate, formatCurrency } from "@/lib/utils";

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
// Types
// ---------------------------------------------------------------------------
type CampaignStatus = "draft" | "active" | "paused" | "completed";

interface CampaignPost {
  id: number;
  content: string;
  platform: string;
  date: string;
  status: string;
}

interface Campaign {
  id: number;
  name: string;
  objective: string;
  status: CampaignStatus;
  platforms: string[];
  budget: number;
  spent: number;
  startDate: string;
  endDate: string;
  impressions: number;
  clicks: number;
  conversions: number;
  ctr: number;
  roi: number;
  posts: CampaignPost[];
  performanceData: { date: string; impressions: number; clicks: number }[];
}

// ---------------------------------------------------------------------------
// Mock Data
// ---------------------------------------------------------------------------
function generateCampaignPerformance(days: number) {
  const data = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const base = 2000 + Math.sin(i * 0.4) * 1000;
    data.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      impressions: Math.round(base + Math.random() * 1500),
      clicks: Math.round(base * 0.08 + Math.random() * 100),
    });
  }
  return data;
}

const campaigns: Campaign[] = [];

const platformIconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter,
  facebook: Facebook,
  youtube: Youtube,
};

const statusConfig: Record<CampaignStatus, { label: string; variant: "success" | "warning" | "danger" | "default" | "info" }> = {
  draft: { label: "Draft", variant: "default" },
  active: { label: "Active", variant: "success" },
  paused: { label: "Paused", variant: "warning" },
  completed: { label: "Completed", variant: "info" },
};

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------
const activeCampaigns = campaigns.filter((c) => c.status === "active").length;
const totalBudget = campaigns.reduce((s, c) => s + c.budget, 0);
const totalSpent = campaigns.reduce((s, c) => s + c.spent, 0);
const avgRoi = campaigns.filter((c) => c.roi > 0).length > 0 ? campaigns.filter((c) => c.roi > 0).reduce((s, c) => s + c.roi, 0) / campaigns.filter((c) => c.roi > 0).length : 0;

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------
function CampaignTooltip({ active, payload, label }: any) {
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

// ---------------------------------------------------------------------------
// Campaigns Page
// ---------------------------------------------------------------------------
const platformOptions = [
  { key: "instagram", label: "Instagram", color: "#E4405F" },
  { key: "facebook", label: "Facebook", color: "#1877F2" },
  { key: "linkedin", label: "LinkedIn", color: "#0A66C2" },
  { key: "twitter", label: "X (Twitter)", color: "#000000" },
  { key: "youtube", label: "YouTube", color: "#FF0000" },
  { key: "tiktok", label: "TikTok", color: "#010101" },
];

export default function CampaignsPage() {
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newCampaign, setNewCampaign] = useState({
    name: "",
    objective: "",
    budget: "",
    startDate: "",
    endDate: "",
    platforms: [] as string[],
  });

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
              Campaigns
            </h1>
            <p className="mt-1 text-sm text-gray-400">
              Manage and track your marketing campaigns
            </p>
          </div>

          <Button
            size="md"
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setShowCreate(true)}
          >
            Create Campaign
          </Button>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Stats Row */}
        {/* ----------------------------------------------------------------- */}
        <motion.div
          variants={staggerContainer}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <motion.div variants={fadeUp}>
            <StatCard
              label="Active Campaigns"
              value={String(activeCampaigns)}
              change={2}
              changeLabel="new this month"
              icon={<Megaphone className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Total Budget"
              value={formatCurrency(totalBudget)}
              icon={<DollarSign className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Budget Spent"
              value={formatCurrency(totalSpent)}
              change={Math.round((totalSpent / totalBudget) * 100)}
              changeLabel="of total budget"
              icon={<Target className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Average ROI"
              value={`${avgRoi.toFixed(1)}x`}
              change={12.4}
              changeLabel="vs last quarter"
              icon={<TrendingUp className="w-5 h-5" />}
            />
          </motion.div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Campaign Cards Grid */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={staggerContainer}>
          <div className="grid gap-4 md:grid-cols-2">
            {campaigns.map((campaign, idx) => {
              const statusInfo = statusConfig[campaign.status];
              const budgetPercent =
                campaign.budget > 0
                  ? Math.round((campaign.spent / campaign.budget) * 100)
                  : 0;

              return (
                <motion.div key={campaign.id} variants={fadeUp}>
                  <GlassCard hover padding="md">
                    {/* Top: Name + Status */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0 mr-3">
                        <h3 className="text-base font-semibold text-white mb-1 line-clamp-1">
                          {campaign.name}
                        </h3>
                        <p className="text-xs text-gray-500 line-clamp-2">
                          {campaign.objective}
                        </p>
                      </div>
                      <Badge variant={statusInfo.variant} dot size="sm">
                        {statusInfo.label}
                      </Badge>
                    </div>

                    {/* Platform Icons */}
                    <div className="flex items-center gap-2 mb-4">
                      {campaign.platforms.map((platform) => {
                        const Icon = platformIconMap[platform];
                        if (!Icon) return null;
                        return (
                          <div
                            key={platform}
                            className="w-7 h-7 rounded-lg flex items-center justify-center bg-white/5 border border-white/10"
                          >
                            <Icon className="w-3.5 h-3.5 text-gray-400" />
                          </div>
                        );
                      })}
                    </div>

                    {/* Budget Bar */}
                    <div className="mb-4">
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="text-gray-400">Budget</span>
                        <span className="text-gray-300 font-medium">
                          {formatCurrency(campaign.spent)}{" "}
                          <span className="text-gray-500">
                            / {formatCurrency(campaign.budget)}
                          </span>
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${budgetPercent}%` }}
                          transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 + idx * 0.05 }}
                          className={cn(
                            "h-full rounded-full",
                            budgetPercent >= 90
                              ? "bg-gradient-to-r from-red-500 to-rose-500"
                              : budgetPercent >= 60
                              ? "bg-gradient-to-r from-amber-500 to-orange-500"
                              : "bg-gradient-to-r from-purple-500 to-blue-500"
                          )}
                        />
                      </div>
                    </div>

                    {/* Date Range */}
                    <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-4">
                      <Calendar className="w-3 h-3" />
                      <span>
                        {formatDate(campaign.startDate)} - {formatDate(campaign.endDate)}
                      </span>
                    </div>

                    {/* Key Metrics */}
                    {campaign.status !== "draft" && (
                      <div className="grid grid-cols-3 gap-3 mb-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-0.5">Impressions</p>
                          <p className="text-sm font-semibold text-white">
                            {formatNumber(campaign.impressions)}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-0.5">Clicks</p>
                          <p className="text-sm font-semibold text-white">
                            {formatNumber(campaign.clicks)}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-0.5">Conversions</p>
                          <p className="text-sm font-semibold text-white">
                            {formatNumber(campaign.conversions)}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      {campaign.status === "active" && (
                        <Button size="sm" variant="ghost" icon={<Pause className="w-3.5 h-3.5" />}>
                          Pause
                        </Button>
                      )}
                      {campaign.status === "paused" && (
                        <Button size="sm" variant="ghost" icon={<Play className="w-3.5 h-3.5" />}>
                          Resume
                        </Button>
                      )}
                      {campaign.status !== "completed" && (
                        <Button size="sm" variant="ghost" icon={<Edit3 className="w-3.5 h-3.5" />}>
                          Edit
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Eye className="w-3.5 h-3.5" />}
                        onClick={() => setSelectedCampaign(campaign)}
                      >
                        View Details
                      </Button>
                    </div>
                  </GlassCard>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </motion.div>

      {/* ------------------------------------------------------------------- */}
      {/* Campaign Detail Modal */}
      {/* ------------------------------------------------------------------- */}
      <Modal
        isOpen={!!selectedCampaign}
        onClose={() => setSelectedCampaign(null)}
        title={selectedCampaign?.name ?? "Campaign Details"}
        size="xl"
      >
        {selectedCampaign && (
          <div className="space-y-6">
            {/* Status + Objective */}
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Badge
                  variant={statusConfig[selectedCampaign.status].variant}
                  dot
                >
                  {statusConfig[selectedCampaign.status].label}
                </Badge>
                <span className="text-xs text-gray-500">
                  {formatDate(selectedCampaign.startDate)} -{" "}
                  {formatDate(selectedCampaign.endDate)}
                </span>
              </div>
              <p className="text-sm text-gray-400">{selectedCampaign.objective}</p>
            </div>

            {/* Full Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  Impressions
                </p>
                <p className="text-lg font-bold text-white">
                  {formatNumber(selectedCampaign.impressions)}
                </p>
              </div>
              <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  Clicks
                </p>
                <p className="text-lg font-bold text-white">
                  {formatNumber(selectedCampaign.clicks)}
                </p>
              </div>
              <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  CTR
                </p>
                <p className="text-lg font-bold text-white">
                  {selectedCampaign.ctr}%
                </p>
              </div>
              <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  ROI
                </p>
                <p className="text-lg font-bold text-white">
                  {selectedCampaign.roi}x
                </p>
              </div>
            </div>

            {/* Budget Details */}
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                Budget Details
              </p>
              <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-400">Total Budget</span>
                  <span className="text-white font-medium">
                    {formatCurrency(selectedCampaign.budget)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-400">Spent</span>
                  <span className="text-white font-medium">
                    {formatCurrency(selectedCampaign.spent)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm mb-3">
                  <span className="text-gray-400">Remaining</span>
                  <span className="text-emerald-400 font-medium">
                    {formatCurrency(selectedCampaign.budget - selectedCampaign.spent)}
                  </span>
                </div>
                <div className="h-2.5 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      selectedCampaign.spent / selectedCampaign.budget >= 0.9
                        ? "bg-gradient-to-r from-red-500 to-rose-500"
                        : "bg-gradient-to-r from-purple-500 to-blue-500"
                    )}
                    style={{
                      width: `${Math.round(
                        (selectedCampaign.spent / selectedCampaign.budget) * 100
                      )}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Performance Chart */}
            {selectedCampaign.performanceData.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                  Performance Over Time
                </p>
                <div className="h-[220px] -mx-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={selectedCampaign.performanceData}>
                      <defs>
                        <linearGradient
                          id="gradModalImp"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#A855F7"
                            stopOpacity={0.3}
                          />
                          <stop
                            offset="100%"
                            stopColor="#A855F7"
                            stopOpacity={0}
                          />
                        </linearGradient>
                        <linearGradient
                          id="gradModalClk"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#3B82F6"
                            stopOpacity={0.3}
                          />
                          <stop
                            offset="100%"
                            stopColor="#3B82F6"
                            stopOpacity={0}
                          />
                        </linearGradient>
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
                        tick={{ fill: "#6B7280", fontSize: 10 }}
                        dy={8}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#6B7280", fontSize: 10 }}
                        tickFormatter={(v: number) => formatNumber(v)}
                        dx={-8}
                        width={45}
                      />
                      <Tooltip content={<CampaignTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="impressions"
                        stroke="#A855F7"
                        strokeWidth={2}
                        fill="url(#gradModalImp)"
                        dot={false}
                        activeDot={{
                          r: 4,
                          fill: "#A855F7",
                          stroke: "#1E1B4B",
                          strokeWidth: 2,
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="clicks"
                        stroke="#3B82F6"
                        strokeWidth={2}
                        fill="url(#gradModalClk)"
                        dot={false}
                        activeDot={{
                          r: 4,
                          fill: "#3B82F6",
                          stroke: "#1E1B4B",
                          strokeWidth: 2,
                        }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex items-center gap-6 mt-2">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-purple-500" />
                    <span className="text-xs text-gray-400">Impressions</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-blue-500" />
                    <span className="text-xs text-gray-400">Clicks</span>
                  </div>
                </div>
              </div>
            )}

            {/* Associated Posts */}
            {selectedCampaign.posts.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                  Campaign Posts ({selectedCampaign.posts.length})
                </p>
                <div className="space-y-2">
                  {selectedCampaign.posts.map((post) => {
                    const PlatformIcon = platformIconMap[post.platform] ?? Eye;
                    return (
                      <div
                        key={post.id}
                        className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]"
                      >
                        <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                          <PlatformIcon className="w-4 h-4 text-gray-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-300 line-clamp-1">
                            {post.content}
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {formatDate(post.date)}
                          </p>
                        </div>
                        <Badge variant="success" size="sm">
                          {post.status}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Empty posts state */}
            {selectedCampaign.posts.length === 0 && (
              <div className="text-center py-8">
                <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3">
                  <BarChart3 className="w-5 h-5 text-gray-500" />
                </div>
                <p className="text-sm text-gray-400">No posts yet</p>
                <p className="text-xs text-gray-500 mt-1">
                  Posts will appear here once the campaign launches
                </p>
              </div>
            )}
          </div>
        )}
      </Modal>
      {/* Create Campaign Modal */}
      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        title="Create Campaign"
        size="lg"
      >
        <div className="space-y-5">
          <Input
            label="Campaign Name"
            placeholder="e.g., Spring Product Launch"
            value={newCampaign.name}
            onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })}
          />

          <div>
            <label className="mb-1.5 block text-sm font-medium" style={{ color: "#374151" }}>
              Objective
            </label>
            <textarea
              placeholder="What's the goal of this campaign?"
              value={newCampaign.objective}
              onChange={(e) => setNewCampaign({ ...newCampaign, objective: e.target.value })}
              rows={3}
              style={{
                backgroundColor: "#ffffff",
                color: "#1f2937",
                border: "1px solid #d1d5db",
              }}
              className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all placeholder:text-gray-400 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/10"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Budget ($)"
              type="number"
              placeholder="5000"
              value={newCampaign.budget}
              onChange={(e) => setNewCampaign({ ...newCampaign, budget: e.target.value })}
            />
            <div />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Start Date"
              type="date"
              value={newCampaign.startDate}
              onChange={(e) => setNewCampaign({ ...newCampaign, startDate: e.target.value })}
            />
            <Input
              label="End Date"
              type="date"
              value={newCampaign.endDate}
              onChange={(e) => setNewCampaign({ ...newCampaign, endDate: e.target.value })}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium" style={{ color: "#374151" }}>
              Target Platforms
            </label>
            <div className="flex flex-wrap gap-2">
              {platformOptions.map((p) => {
                const selected = newCampaign.platforms.includes(p.key);
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() =>
                      setNewCampaign({
                        ...newCampaign,
                        platforms: selected
                          ? newCampaign.platforms.filter((x) => x !== p.key)
                          : [...newCampaign.platforms, p.key],
                      })
                    }
                    className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all"
                    style={{
                      backgroundColor: selected ? p.color + "10" : "#ffffff",
                      borderColor: selected ? p.color : "#e5e7eb",
                      color: selected ? p.color : "#6b7280",
                    }}
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: p.color }}
                    />
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => {
                alert("Campaign created! (Demo - would call API in production)");
                setShowCreate(false);
                setNewCampaign({ name: "", objective: "", budget: "", startDate: "", endDate: "", platforms: [] });
              }}
            >
              Create Campaign
            </Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
