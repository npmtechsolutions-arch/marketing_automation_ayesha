import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Megaphone,
  DollarSign,
  TrendingUp,
  Target,
  Pause,
  Play,
  Eye,
  Calendar,
  RefreshCw,
  Trash2,
  CheckCircle,
} from "lucide-react";
import { Instagram, Linkedin, Twitter, Facebook, Youtube } from "@/components/shared/SocialIcons";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { cn, formatNumber, formatDate, formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";

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
type CampaignStatus = "draft" | "active" | "paused" | "completed";

interface Campaign {
  id: string;
  name: string;
  objective: string | null;
  status: CampaignStatus;
  platforms: { type: string }[];
  budget_total: number | null;
  budget_daily: number | null;
  budget_spent: number;
  start_date: string | null;
  end_date: string | null;
  results: Record<string, any> | null;
  created_at: string;
}

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

const platformOptions = [
  { key: "instagram", label: "Instagram", color: "#E4405F" },
  { key: "facebook", label: "Facebook", color: "#1877F2" },
  { key: "linkedin", label: "LinkedIn", color: "#0A66C2" },
  { key: "twitter", label: "X (Twitter)", color: "#000000" },
  { key: "youtube", label: "YouTube", color: "#FF0000" },
  { key: "tiktok", label: "TikTok", color: "#010101" },
];

// ---------------------------------------------------------------------------
// Campaigns Page
// ---------------------------------------------------------------------------
export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newCampaign, setNewCampaign] = useState({
    name: "",
    objective: "",
    budget: "",
    startDate: "",
    endDate: "",
    platforms: [] as string[],
  });

  const accountId = localStorage.getItem("account_id");

  // ---------------------------------------------------------------------------
  // Fetch campaigns
  // ---------------------------------------------------------------------------
  const fetchCampaigns = async () => {
    if (!accountId) return;
    try {
      setLoading(true);
      const res: any = await api.get(`/accounts/${accountId}/campaigns/`);
      const payload = res.data || res;
      setCampaigns(payload.items || []);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
      showError("Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCampaigns(); }, []);

  // ---------------------------------------------------------------------------
  // Create campaign
  // ---------------------------------------------------------------------------
  const handleCreate = async () => {
    if (!newCampaign.name.trim()) { showError("Campaign name is required"); return; }
    try {
      setCreating(true);
      const payload: any = {
        name: newCampaign.name.trim(),
        objective: newCampaign.objective || null,
        platforms: newCampaign.platforms.map((p) => ({ type: p })),
      };
      if (newCampaign.budget) payload.budget_total = parseFloat(newCampaign.budget);
      if (newCampaign.startDate) payload.start_date = newCampaign.startDate;
      if (newCampaign.endDate) payload.end_date = newCampaign.endDate;

      const res: any = await api.post(`/accounts/${accountId}/campaigns/`, payload);
      const created: Campaign = res.data || res;
      setCampaigns((prev) => [created, ...prev]);
      setShowCreate(false);
      setNewCampaign({ name: "", objective: "", budget: "", startDate: "", endDate: "", platforms: [] });
      showSuccess("Campaign created successfully!");
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to create campaign");
    } finally {
      setCreating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Status actions
  // ---------------------------------------------------------------------------
  const updateStatus = async (id: string, action: "activate" | "pause" | "complete") => {
    try {
      const res: any = await api.post(`/accounts/${accountId}/campaigns/${id}/${action}`);
      const updated: Campaign = res.data || res;
      setCampaigns((prev) => prev.map((c) => c.id === id ? updated : c));
      if (selectedCampaign?.id === id) setSelectedCampaign(updated);
      showSuccess(`Campaign ${action}d!`);
    } catch (err: any) {
      showError(err?.response?.data?.detail || `Failed to ${action} campaign`);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/accounts/${accountId}/campaigns/${id}`);
      setCampaigns((prev) => prev.filter((c) => c.id !== id));
      setSelectedCampaign(null);
      showSuccess("Campaign deleted");
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to delete campaign");
    }
  };

  // ---------------------------------------------------------------------------
  // Stats computed from real data
  // ---------------------------------------------------------------------------
  const activeCampaigns = campaigns.filter((c) => c.status === "active").length;
  const totalBudget = campaigns.reduce((s, c) => s + (c.budget_total || 0), 0);
  const totalSpent = campaigns.reduce((s, c) => s + c.budget_spent, 0);

  return (
    <DashboardLayout>
      <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6 pb-8">
        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white sm:text-3xl">Campaigns</h1>
            <p className="mt-1 text-sm text-gray-400">Manage and track your marketing campaigns</p>
          </div>
          <Button size="md" variant="primary" icon={<Plus className="w-4 h-4" />} onClick={() => setShowCreate(true)}>
            Create Campaign
          </Button>
        </motion.div>

        {/* Stats Row */}
        <motion.div variants={staggerContainer} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <motion.div variants={fadeUp}>
            <StatCard label="Active Campaigns" value={String(activeCampaigns)} icon={<Megaphone className="w-5 h-5" />} />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard label="Total Budget" value={formatCurrency(totalBudget)} icon={<DollarSign className="w-5 h-5" />} />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard
              label="Budget Spent"
              value={formatCurrency(totalSpent)}
              change={totalBudget > 0 ? Math.round((totalSpent / totalBudget) * 100) : undefined}
              changeLabel="of total budget"
              icon={<Target className="w-5 h-5" />}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <StatCard label="Total Campaigns" value={String(campaigns.length)} icon={<TrendingUp className="w-5 h-5" />} />
          </motion.div>
        </motion.div>

        {/* Campaigns Grid */}
        {loading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-52 rounded-2xl bg-white/5 animate-pulse" />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <div className="text-center py-12">
                <Megaphone className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400 mb-2">No campaigns yet</p>
                <p className="text-sm text-slate-500 mb-5">Create your first campaign to start tracking performance</p>
                <Button size="sm" variant="primary" icon={<Plus className="w-4 h-4" />} onClick={() => setShowCreate(true)}>
                  Create Campaign
                </Button>
              </div>
            </GlassCard>
          </motion.div>
        ) : (
          <motion.div variants={staggerContainer}>
            <div className="grid gap-4 md:grid-cols-2">
              <AnimatePresence>
                {campaigns.map((campaign, idx) => {
                  const statusInfo = statusConfig[campaign.status] || statusConfig.draft;
                  const budgetPercent = campaign.budget_total
                    ? Math.min(100, Math.round((campaign.budget_spent / campaign.budget_total) * 100))
                    : 0;
                  const platformList = campaign.platforms?.map((p: any) => p.type || p) || [];

                  return (
                    <motion.div key={campaign.id} variants={fadeUp}>
                      <GlassCard hover padding="md">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1 min-w-0 mr-3">
                            <h3 className="text-base font-semibold text-white mb-1 line-clamp-1">{campaign.name}</h3>
                            <p className="text-xs text-gray-500 line-clamp-2">{campaign.objective || "No objective set"}</p>
                          </div>
                          <Badge variant={statusInfo.variant} dot size="sm">{statusInfo.label}</Badge>
                        </div>

                        {/* Platform Icons */}
                        {platformList.length > 0 && (
                          <div className="flex items-center gap-2 mb-4">
                            {platformList.map((platform: string) => {
                              const Icon = platformIconMap[platform];
                              if (!Icon) return null;
                              return (
                                <div key={platform} className="w-7 h-7 rounded-lg flex items-center justify-center bg-white/5 border border-white/10">
                                  <Icon className="w-3.5 h-3.5 text-gray-400" />
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {/* Budget Bar */}
                        {campaign.budget_total && campaign.budget_total > 0 ? (
                          <div className="mb-4">
                            <div className="flex items-center justify-between text-xs mb-1.5">
                              <span className="text-gray-400">Budget</span>
                              <span className="text-gray-300 font-medium">
                                {formatCurrency(campaign.budget_spent)}{" "}
                                <span className="text-gray-500">/ {formatCurrency(campaign.budget_total)}</span>
                              </span>
                            </div>
                            <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${budgetPercent}%` }}
                                transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 + idx * 0.05 }}
                                className={cn(
                                  "h-full rounded-full",
                                  budgetPercent >= 90 ? "bg-gradient-to-r from-red-500 to-rose-500"
                                    : budgetPercent >= 60 ? "bg-gradient-to-r from-amber-500 to-orange-500"
                                    : "bg-gradient-to-r from-purple-500 to-blue-500"
                                )}
                              />
                            </div>
                          </div>
                        ) : null}

                        {/* Date Range */}
                        {(campaign.start_date || campaign.end_date) && (
                          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-4">
                            <Calendar className="w-3 h-3" />
                            <span>
                              {campaign.start_date ? formatDate(campaign.start_date) : "?"} —{" "}
                              {campaign.end_date ? formatDate(campaign.end_date) : "Ongoing"}
                            </span>
                          </div>
                        )}

                        {/* Results */}
                        {campaign.results && Object.keys(campaign.results).length > 0 && (
                          <div className="grid grid-cols-3 gap-3 mb-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                            {["impressions", "clicks", "conversions"].map((key) => (
                              campaign.results![key] != null ? (
                                <div key={key} className="text-center">
                                  <p className="text-xs text-gray-500 mb-0.5 capitalize">{key}</p>
                                  <p className="text-sm font-semibold text-white">{formatNumber(campaign.results![key])}</p>
                                </div>
                              ) : null
                            ))}
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex items-center gap-2 flex-wrap">
                          {campaign.status === "active" && (
                            <Button size="sm" variant="ghost" icon={<Pause className="w-3.5 h-3.5" />}
                              onClick={() => updateStatus(campaign.id, "pause")}>Pause</Button>
                          )}
                          {campaign.status === "paused" && (
                            <Button size="sm" variant="ghost" icon={<Play className="w-3.5 h-3.5" />}
                              onClick={() => updateStatus(campaign.id, "activate")}>Resume</Button>
                          )}
                          {campaign.status === "draft" && (
                            <Button size="sm" variant="ghost" icon={<Play className="w-3.5 h-3.5" />}
                              onClick={() => updateStatus(campaign.id, "activate")}>Activate</Button>
                          )}
                          {(campaign.status === "active" || campaign.status === "paused") && (
                            <Button size="sm" variant="ghost" icon={<CheckCircle className="w-3.5 h-3.5" />}
                              onClick={() => updateStatus(campaign.id, "complete")}>Complete</Button>
                          )}
                          {campaign.status === "draft" && (
                            <Button size="sm" variant="ghost" icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                              onClick={() => handleDelete(campaign.id)}>Delete</Button>
                          )}
                          <Button size="sm" variant="secondary" icon={<Eye className="w-3.5 h-3.5" />}
                            onClick={() => setSelectedCampaign(campaign)}>View Details</Button>
                        </div>
                      </GlassCard>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* Campaign Detail Modal */}
      <Modal isOpen={!!selectedCampaign} onClose={() => setSelectedCampaign(null)}
        title={selectedCampaign?.name ?? "Campaign Details"} size="lg">
        {selectedCampaign && (() => {
          const statusInfo = statusConfig[selectedCampaign.status] || statusConfig.draft;
          const platformList = selectedCampaign.platforms?.map((p: any) => p.type || p) || [];
          return (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <Badge variant={statusInfo.variant} dot>{statusInfo.label}</Badge>
                {(selectedCampaign.start_date || selectedCampaign.end_date) && (
                  <span className="text-xs text-gray-500">
                    {selectedCampaign.start_date ? formatDate(selectedCampaign.start_date) : "?"} — {selectedCampaign.end_date ? formatDate(selectedCampaign.end_date) : "Ongoing"}
                  </span>
                )}
              </div>

              {selectedCampaign.objective && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Objective</p>
                  <p className="text-sm text-gray-300">{selectedCampaign.objective}</p>
                </div>
              )}

              {platformList.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Platforms</p>
                  <div className="flex gap-2 flex-wrap">
                    {platformList.map((p: string) => {
                      const Icon = platformIconMap[p];
                      return (
                        <div key={p} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 capitalize">
                          {Icon && <Icon className="w-3.5 h-3.5" />}{p}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {selectedCampaign.budget_total != null && selectedCampaign.budget_total > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Budget Details</p>
                  <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06] space-y-2">
                    {[
                      { label: "Total Budget", value: formatCurrency(selectedCampaign.budget_total), cls: "text-white" },
                      { label: "Spent", value: formatCurrency(selectedCampaign.budget_spent), cls: "text-white" },
                      { label: "Remaining", value: formatCurrency((selectedCampaign.budget_total || 0) - selectedCampaign.budget_spent), cls: "text-emerald-400" },
                    ].map((row) => (
                      <div key={row.label} className="flex items-center justify-between text-sm">
                        <span className="text-gray-400">{row.label}</span>
                        <span className={`font-medium ${row.cls}`}>{row.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedCampaign.results && Object.keys(selectedCampaign.results).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Results</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {Object.entries(selectedCampaign.results).map(([key, val]) => (
                      <div key={key} className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center">
                        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1 capitalize">{key.replace(/_/g, " ")}</p>
                        <p className="text-lg font-bold text-white">{typeof val === "number" ? formatNumber(val) : String(val)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                {selectedCampaign.status === "draft" && (
                  <>
                    <Button size="sm" variant="primary" icon={<Play className="w-3.5 h-3.5" />}
                      onClick={() => updateStatus(selectedCampaign.id, "activate")}>Activate</Button>
                    <Button size="sm" variant="danger" icon={<Trash2 className="w-3.5 h-3.5" />}
                      onClick={() => handleDelete(selectedCampaign.id)}>Delete</Button>
                  </>
                )}
                {selectedCampaign.status === "active" && (
                  <Button size="sm" variant="ghost" icon={<Pause className="w-3.5 h-3.5" />}
                    onClick={() => updateStatus(selectedCampaign.id, "pause")}>Pause</Button>
                )}
                {selectedCampaign.status === "paused" && (
                  <Button size="sm" variant="primary" icon={<Play className="w-3.5 h-3.5" />}
                    onClick={() => updateStatus(selectedCampaign.id, "activate")}>Resume</Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setSelectedCampaign(null)}>Close</Button>
              </div>
            </div>
          );
        })()}
      </Modal>

      {/* Create Campaign Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Campaign" size="lg">
        <div className="space-y-5">
          <Input label="Campaign Name" placeholder="e.g., Spring Product Launch"
            value={newCampaign.name} onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })} />

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400 uppercase tracking-wider">Objective</label>
            <textarea
              placeholder="What's the goal of this campaign?"
              value={newCampaign.objective}
              onChange={(e) => setNewCampaign({ ...newCampaign, objective: e.target.value })}
              rows={3}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input label="Budget ($)" type="number" placeholder="5000"
              value={newCampaign.budget} onChange={(e) => setNewCampaign({ ...newCampaign, budget: e.target.value })} />
            <div />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input label="Start Date" type="date"
              value={newCampaign.startDate} onChange={(e) => setNewCampaign({ ...newCampaign, startDate: e.target.value })} />
            <Input label="End Date" type="date"
              value={newCampaign.endDate} onChange={(e) => setNewCampaign({ ...newCampaign, endDate: e.target.value })} />
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-slate-400 uppercase tracking-wider">Target Platforms</label>
            <div className="flex flex-wrap gap-2">
              {platformOptions.map((p) => {
                const selected = newCampaign.platforms.includes(p.key);
                return (
                  <button key={p.key} type="button"
                    onClick={() => setNewCampaign({
                      ...newCampaign,
                      platforms: selected ? newCampaign.platforms.filter((x) => x !== p.key) : [...newCampaign.platforms, p.key],
                    })}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all ${
                      selected ? "bg-purple-500/20 border-purple-500/40 text-purple-300" : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10"
                    }`}
                  >
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: p.color }} />
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button variant="primary" icon={creating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              onClick={handleCreate} disabled={creating}>
              {creating ? "Creating…" : "Create Campaign"}
            </Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
