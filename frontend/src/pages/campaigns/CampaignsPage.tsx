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
  Pencil,
  FileText,
  X,
  Loader2,
  Check,
  Heart,
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
import api, { getAccountId } from "@/lib/api";
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
  post_count?: number;
  created_at: string;
}

interface LinkedPost {
  id: string;
  title: string | null;
  content: string;
  status: string;
  platforms: string[];
  published_at: string | null;
  reach: number;
  engagement: number;
}

interface CampaignStats {
  post_count: number;
  published_count: number;
  scheduled_count: number;
  reach: number;
  impressions: number;
  engagement: number;
  clicks: number;
  engagement_rate: number;
  budget_total: number | null;
  budget_spent: number;
  budget_remaining: number | null;
}

const platformIconMap: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
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
];

const emptyForm = { name: "", objective: "", budget: "", startDate: "", endDate: "", platforms: [] as string[] };

// ---------------------------------------------------------------------------
// Campaigns Page
// ---------------------------------------------------------------------------
export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [accountId, setAccountId] = useState<string | null>(null);

  // Create / edit form
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);

  // Detail hub
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [linkedPosts, setLinkedPosts] = useState<LinkedPost[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [spendInput, setSpendInput] = useState("");
  const [savingSpend, setSavingSpend] = useState(false);

  // Add-posts picker
  const [showAddPosts, setShowAddPosts] = useState(false);
  const [availablePosts, setAvailablePosts] = useState<LinkedPost[]>([]);
  const [availableLoading, setAvailableLoading] = useState(false);
  const [selectedPostIds, setSelectedPostIds] = useState<string[]>([]);
  const [attaching, setAttaching] = useState(false);

  // ---------------------------------------------------------------------------
  // Fetch campaigns
  // ---------------------------------------------------------------------------
  const fetchCampaigns = async () => {
    const activeAccountId = await getAccountId();
    setAccountId(activeAccountId);
    if (!activeAccountId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/campaigns/`);
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
  // Create / edit campaign
  // ---------------------------------------------------------------------------
  const openCreate = () => {
    setFormMode("create");
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  };

  const openEdit = (c: Campaign) => {
    setFormMode("edit");
    setEditingId(c.id);
    setForm({
      name: c.name,
      objective: c.objective || "",
      budget: c.budget_total != null ? String(c.budget_total) : "",
      startDate: c.start_date || "",
      endDate: c.end_date || "",
      platforms: (c.platforms || []).map((p: any) => p.type || p),
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) { showError("Campaign name is required"); return; }
    try {
      setSaving(true);
      const payload: any = {
        name: form.name.trim(),
        objective: form.objective || null,
        platforms: form.platforms.map((p) => ({ type: p })),
        budget_total: form.budget ? parseFloat(form.budget) : null,
        start_date: form.startDate || null,
        end_date: form.endDate || null,
      };

      if (formMode === "edit" && editingId) {
        const res: any = await api.put(`/accounts/${accountId}/campaigns/${editingId}`, payload);
        const updated: Campaign = res.data || res;
        setCampaigns((prev) => prev.map((c) => (c.id === editingId ? updated : c)));
        if (selectedCampaign?.id === editingId) setSelectedCampaign(updated);
        showSuccess("Campaign updated!");
      } else {
        const res: any = await api.post(`/accounts/${accountId}/campaigns/`, payload);
        const created: Campaign = res.data || res;
        setCampaigns((prev) => [created, ...prev]);
        showSuccess("Campaign created successfully!");
      }
      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
    } catch (err: any) {
      showError(err?.response?.data?.detail || `Failed to ${formMode === "edit" ? "update" : "create"} campaign`);
    } finally {
      setSaving(false);
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
  // Detail hub: stats + linked posts + spend
  // ---------------------------------------------------------------------------
  const loadDetail = async (id: string) => {
    const aid = accountId || (await getAccountId());
    if (!aid) return;
    setDetailLoading(true);
    try {
      const [statsRes, postsRes] = await Promise.allSettled([
        api.get(`/accounts/${aid}/campaigns/${id}/stats`),
        api.get(`/accounts/${aid}/campaigns/${id}/posts`),
      ]);
      if (statsRes.status === "fulfilled") setStats((statsRes.value as any).data ?? statsRes.value);
      if (postsRes.status === "fulfilled") setLinkedPosts((postsRes.value as any).data ?? postsRes.value ?? []);
    } finally {
      setDetailLoading(false);
    }
  };

  const openDetail = (c: Campaign) => {
    setSelectedCampaign(c);
    setStats(null);
    setLinkedPosts([]);
    setSpendInput("");
    loadDetail(c.id);
  };

  const closeDetail = () => {
    setSelectedCampaign(null);
    setStats(null);
    setLinkedPosts([]);
  };

  const detachPost = async (postId: string) => {
    if (!selectedCampaign) return;
    try {
      await api.delete(`/accounts/${accountId}/campaigns/${selectedCampaign.id}/posts/${postId}`);
      setLinkedPosts((prev) => prev.filter((p) => p.id !== postId));
      loadDetail(selectedCampaign.id);
      setCampaigns((prev) => prev.map((c) => c.id === selectedCampaign.id ? { ...c, post_count: Math.max(0, (c.post_count ?? 1) - 1) } : c));
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to remove post");
    }
  };

  const logSpend = async () => {
    if (!selectedCampaign) return;
    const amt = parseFloat(spendInput);
    if (isNaN(amt) || amt <= 0) { showError("Enter a spend amount"); return; }
    setSavingSpend(true);
    try {
      const res: any = await api.post(`/accounts/${accountId}/campaigns/${selectedCampaign.id}/spend`, { amount: amt, mode: "add" });
      const updated: Campaign = res.data || res;
      setCampaigns((prev) => prev.map((c) => c.id === updated.id ? updated : c));
      setSelectedCampaign(updated);
      setSpendInput("");
      loadDetail(updated.id);
      showSuccess("Spend recorded");
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to record spend");
    } finally {
      setSavingSpend(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Add posts picker
  // ---------------------------------------------------------------------------
  const openAddPosts = async () => {
    if (!selectedCampaign) return;
    setShowAddPosts(true);
    setSelectedPostIds([]);
    setAvailableLoading(true);
    try {
      const res: any = await api.get(`/accounts/${accountId}/campaigns/${selectedCampaign.id}/available-posts`);
      setAvailablePosts((res.data ?? res ?? []) as LinkedPost[]);
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to load posts");
    } finally {
      setAvailableLoading(false);
    }
  };

  const togglePostSelection = (id: string) => {
    setSelectedPostIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  };

  const attachPosts = async () => {
    if (!selectedCampaign || selectedPostIds.length === 0) return;
    setAttaching(true);
    try {
      await api.post(`/accounts/${accountId}/campaigns/${selectedCampaign.id}/posts`, { post_ids: selectedPostIds });
      setShowAddPosts(false);
      loadDetail(selectedCampaign.id);
      setCampaigns((prev) => prev.map((c) => c.id === selectedCampaign.id ? { ...c, post_count: (c.post_count ?? 0) + selectedPostIds.length } : c));
      showSuccess(`${selectedPostIds.length} post(s) added`);
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to add posts");
    } finally {
      setAttaching(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Stats computed from real data
  // ---------------------------------------------------------------------------
  const activeCampaigns = campaigns.filter((c) => c.status === "active").length;
  const totalBudget = campaigns.reduce((s, c) => s + (c.budget_total || 0), 0);
  const totalSpent = campaigns.reduce((s, c) => s + c.budget_spent, 0);

  const postStatusVariant = (s: string): "success" | "warning" | "info" | "default" | "danger" =>
    s === "published" || s === "partially_published" ? "success"
      : s === "scheduled" ? "info"
      : s === "failed" ? "danger"
      : s === "pending_approval" || s === "approved" ? "warning"
      : "default";

  const renderPostRow = (p: LinkedPost, opts: { selectable?: boolean } = {}) => {
    const selected = selectedPostIds.includes(p.id);
    return (
      <div
        key={p.id}
        onClick={opts.selectable ? () => togglePostSelection(p.id) : undefined}
        className={cn("flex items-center gap-3 rounded-xl p-3", opts.selectable && "cursor-pointer")}
        style={{
          backgroundColor: "var(--sidebar-hover-bg)",
          border: `1px solid ${opts.selectable && selected ? "rgba(124,58,237,0.45)" : "var(--surface-border)"}`,
        }}
      >
        {opts.selectable && (
          <div
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
            style={{
              backgroundColor: selected ? "#7c3aed" : "transparent",
              border: `1px solid ${selected ? "#7c3aed" : "var(--surface-border)"}`,
            }}
          >
            {selected && <Check className="h-3 w-3 text-white" />}
          </div>
        )}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: "rgba(124,58,237,0.12)", border: "1px solid var(--surface-border)" }}>
          <FileText className="h-4 w-4" style={{ color: "#7c3aed" }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" style={{ color: "var(--page-heading)" }}>
            {p.title || p.content || "Untitled post"}
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <Badge variant={postStatusVariant(p.status)} size="sm">{p.status.replace(/_/g, " ")}</Badge>
            {p.platforms.slice(0, 3).map((pl) => (
              <span key={pl} className="text-[11px] capitalize" style={{ color: "var(--page-text-muted)" }}>{pl}</span>
            ))}
          </div>
        </div>
        {!opts.selectable && (
          <>
            <div className="hidden text-right sm:block">
              <p className="text-xs font-semibold tabular-nums" style={{ color: "var(--page-text)" }}>{formatNumber(p.reach)}</p>
              <p className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>reach</p>
            </div>
            <div className="hidden text-right sm:block">
              <p className="text-xs font-semibold tabular-nums" style={{ color: "#10b981" }}>{formatNumber(p.engagement)}</p>
              <p className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>engage</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); detachPost(p.id); }}
              className="rounded-lg p-1.5 transition-colors cursor-pointer hover:text-red-400 hover:bg-red-500/10"
              style={{ color: "var(--page-text-muted)" }}
              title="Remove from campaign"
            >
              <X className="h-4 w-4" />
            </button>
          </>
        )}
        {opts.selectable && p.reach > 0 && (
          <span className="text-[11px] tabular-nums" style={{ color: "var(--page-text-muted)" }}>{formatNumber(p.reach)} reach</span>
        )}
      </div>
    );
  };

  return (
    <DashboardLayout>
      <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6 pb-8">
        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl" style={{ color: "var(--page-heading)" }}>Campaigns</h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>Group your posts into campaigns and track their combined performance</p>
          </div>
          <Button size="md" variant="primary" icon={<Plus className="w-4 h-4" />} onClick={openCreate}>
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
              <div key={i} className="h-52 rounded-2xl animate-pulse" style={{ backgroundColor: "var(--shimmer-bg)" }} />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <motion.div variants={fadeUp}>
            <GlassCard padding="lg">
              <div className="text-center py-12">
                <Megaphone className="w-12 h-12 mx-auto mb-4" style={{ color: "var(--page-text-muted)", opacity: 0.6 }} />
                <p className="mb-2 font-medium" style={{ color: "var(--page-text-secondary)" }}>No campaigns yet</p>
                <p className="text-sm mb-5" style={{ color: "var(--page-text-muted)" }}>Create your first campaign, then add the posts you want to track together</p>
                <Button size="sm" variant="primary" icon={<Plus className="w-4 h-4" />} onClick={openCreate}>
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
                  const postCount = campaign.post_count ?? 0;
                  const canEdit = campaign.status === "draft" || campaign.status === "paused";

                  return (
                    <motion.div key={campaign.id} variants={fadeUp}>
                      <GlassCard hover padding="md">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1 min-w-0 mr-3">
                            <h3 className="text-base font-semibold mb-1 line-clamp-1" style={{ color: "var(--page-heading)" }}>{campaign.name}</h3>
                            <p className="text-xs line-clamp-2" style={{ color: "var(--page-text-muted)" }}>{campaign.objective || "No objective set"}</p>
                          </div>
                          <Badge variant={statusInfo.variant} dot size="sm">{statusInfo.label}</Badge>
                        </div>

                        {/* Platform Icons + post count */}
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            {platformList.map((platform: string) => {
                              const Icon = platformIconMap[platform];
                              if (!Icon) return null;
                              return (
                                <div key={platform} className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                                  <Icon className="w-3.5 h-3.5" style={{ color: "var(--page-text-muted)" }} />
                                </div>
                              );
                            })}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
                            <FileText className="w-3.5 h-3.5" />
                            <span className="tabular-nums">{postCount}</span> post{postCount !== 1 ? "s" : ""}
                          </div>
                        </div>

                        {/* Budget Bar */}
                        {campaign.budget_total && campaign.budget_total > 0 ? (
                          <div className="mb-4">
                            <div className="flex items-center justify-between text-xs mb-1.5">
                              <span style={{ color: "var(--page-text-secondary)" }}>Budget</span>
                              <span className="font-medium tabular-nums" style={{ color: "var(--page-text)" }}>
                                {formatCurrency(campaign.budget_spent)}{" "}
                                <span style={{ color: "var(--page-text-muted)" }}>/ {formatCurrency(campaign.budget_total)}</span>
                              </span>
                            </div>
                            <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--sidebar-hover-bg)" }}>
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
                          <div className="flex items-center gap-1.5 text-xs mb-4" style={{ color: "var(--page-text-muted)" }}>
                            <Calendar className="w-3 h-3" />
                            <span>
                              {campaign.start_date ? formatDate(campaign.start_date) : "?"} —{" "}
                              {campaign.end_date ? formatDate(campaign.end_date) : "Ongoing"}
                            </span>
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
                          {canEdit && (
                            <Button size="sm" variant="ghost" icon={<Pencil className="w-3.5 h-3.5" />}
                              onClick={() => openEdit(campaign)}>Edit</Button>
                          )}
                          {campaign.status === "draft" && (
                            <Button size="sm" variant="ghost" icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                              onClick={() => handleDelete(campaign.id)}>Delete</Button>
                          )}
                          <Button size="sm" variant="secondary" icon={<Eye className="w-3.5 h-3.5" />}
                            onClick={() => openDetail(campaign)}>View Details</Button>
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

      {/* Campaign Detail Modal (hub) */}
      <Modal isOpen={!!selectedCampaign} onClose={closeDetail}
        title={selectedCampaign?.name ?? "Campaign Details"} size="lg">
        {selectedCampaign && (() => {
          const statusInfo = statusConfig[selectedCampaign.status] || statusConfig.draft;
          const platformList = selectedCampaign.platforms?.map((p: any) => p.type || p) || [];
          const budgetTotal = selectedCampaign.budget_total || 0;
          const budgetPercent = budgetTotal > 0 ? Math.min(100, Math.round((selectedCampaign.budget_spent / budgetTotal) * 100)) : 0;
          const statCells = [
            { label: "Posts", value: stats ? String(stats.post_count) : "—" },
            { label: "Reach", value: stats ? formatNumber(stats.reach) : "—" },
            { label: "Engagement", value: stats ? formatNumber(stats.engagement) : "—" },
            { label: "Eng. Rate", value: stats ? `${(stats.engagement_rate * 100).toFixed(2)}%` : "—" },
          ];
          return (
            <div className="space-y-5">
              {/* Status + dates */}
              <div className="flex items-center gap-3">
                <Badge variant={statusInfo.variant} dot>{statusInfo.label}</Badge>
                {(selectedCampaign.start_date || selectedCampaign.end_date) && (
                  <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                    {selectedCampaign.start_date ? formatDate(selectedCampaign.start_date) : "?"} — {selectedCampaign.end_date ? formatDate(selectedCampaign.end_date) : "Ongoing"}
                  </span>
                )}
                {detailLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: "#7c3aed" }} />}
              </div>

              {selectedCampaign.objective && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "var(--page-text-muted)" }}>Objective</p>
                  <p className="text-sm" style={{ color: "var(--page-text)" }}>{selectedCampaign.objective}</p>
                </div>
              )}

              {/* Performance stats */}
              <div>
                <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--page-text-muted)" }}>Performance</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {statCells.map((s) => (
                    <div key={s.label} className="rounded-xl p-3 text-center" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                      <p className="text-lg font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>{s.value}</p>
                      <p className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: "var(--page-text-muted)" }}>{s.label}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[11px]" style={{ color: "var(--page-text-muted)" }}>
                  Aggregated from the posts linked below (updates as their analytics come in).
                </p>
              </div>

              {/* Budget + spend logging */}
              <div>
                <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--page-text-muted)" }}>Budget</p>
                <div className="rounded-xl p-4 space-y-3" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                  <div className="flex items-center justify-between text-sm">
                    <span style={{ color: "var(--page-text-secondary)" }}>Spent</span>
                    <span className="font-medium tabular-nums" style={{ color: "var(--page-heading)" }}>
                      {formatCurrency(selectedCampaign.budget_spent)}
                      {budgetTotal > 0 && <span style={{ color: "var(--page-text-muted)" }}> / {formatCurrency(budgetTotal)}</span>}
                    </span>
                  </div>
                  {budgetTotal > 0 && (
                    <>
                      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--surface-bg)" }}>
                        <div className={cn("h-full rounded-full", budgetPercent >= 90 ? "bg-gradient-to-r from-red-500 to-rose-500" : budgetPercent >= 60 ? "bg-gradient-to-r from-amber-500 to-orange-500" : "bg-gradient-to-r from-purple-500 to-blue-500")} style={{ width: `${budgetPercent}%` }} />
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span style={{ color: "var(--page-text-muted)" }}>Remaining</span>
                        <span className="tabular-nums" style={{ color: "#10b981" }}>{formatCurrency(budgetTotal - selectedCampaign.budget_spent)}</span>
                      </div>
                    </>
                  )}
                  <div className="flex items-center gap-2 pt-1">
                    <div className="relative flex-1">
                      <DollarSign className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--page-text-muted)" }} />
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={spendInput}
                        onChange={(e) => setSpendInput(e.target.value)}
                        placeholder="Add spend amount"
                        className="w-full rounded-lg py-2 pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)] focus:border-[rgba(124,58,237,0.50)]"
                        style={{ border: "1px solid var(--surface-border)", backgroundColor: "var(--input-bg)", color: "var(--page-text)" }}
                      />
                    </div>
                    <Button size="sm" variant="secondary" disabled={savingSpend} onClick={logSpend}
                      icon={savingSpend ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}>
                      Log
                    </Button>
                  </div>
                </div>
              </div>

              {platformList.length > 0 && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--page-text-muted)" }}>Platforms</p>
                  <div className="flex gap-2 flex-wrap">
                    {platformList.map((p: string) => {
                      const Icon = platformIconMap[p];
                      return (
                        <div key={p} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs capitalize" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)", color: "var(--page-text)" }}>
                          {Icon && <Icon className="w-3.5 h-3.5" />}{p}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Linked posts */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
                    Linked Posts ({linkedPosts.length})
                  </p>
                  <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={openAddPosts}>
                    Add Posts
                  </Button>
                </div>
                {linkedPosts.length > 0 ? (
                  <div className="space-y-2">
                    {linkedPosts.map((p) => renderPostRow(p))}
                  </div>
                ) : (
                  <div className="rounded-xl p-6 text-center" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px dashed var(--surface-border)" }}>
                    <Heart className="mx-auto mb-2 h-6 w-6" style={{ color: "var(--page-text-muted)", opacity: 0.5 }} />
                    <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>No posts linked yet</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--page-text-muted)" }}>Click "Add Posts" to attach content and start tracking performance.</p>
                  </div>
                )}
              </div>

              {/* Footer actions */}
              <div className="flex gap-3 pt-2 flex-wrap">
                {(selectedCampaign.status === "draft" || selectedCampaign.status === "paused") && (
                  <Button size="sm" variant="ghost" icon={<Pencil className="w-3.5 h-3.5" />}
                    onClick={() => openEdit(selectedCampaign)}>Edit</Button>
                )}
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
                {(selectedCampaign.status === "active" || selectedCampaign.status === "paused") && (
                  <Button size="sm" variant="ghost" icon={<CheckCircle className="w-3.5 h-3.5" />}
                    onClick={() => updateStatus(selectedCampaign.id, "complete")}>Complete</Button>
                )}
                <Button size="sm" variant="ghost" onClick={closeDetail} className="ml-auto">Close</Button>
              </div>
            </div>
          );
        })()}
      </Modal>

      {/* Create / Edit Campaign Modal */}
      <Modal isOpen={showForm} onClose={() => setShowForm(false)} title={formMode === "edit" ? "Edit Campaign" : "Create Campaign"} size="lg">
        <div className="space-y-5">
          <Input label="Campaign Name" placeholder="e.g., Spring Product Launch"
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />

          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Objective</label>
            <textarea
              placeholder="What's the goal of this campaign?"
              value={form.objective}
              onChange={(e) => setForm({ ...form, objective: e.target.value })}
              rows={3}
              className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all resize-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)] focus:border-[rgba(124,58,237,0.50)]"
              style={{ border: "1px solid var(--surface-border)", backgroundColor: "var(--input-bg)", color: "var(--page-text)" }}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input label="Budget ($)" type="number" placeholder="5000"
              value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} />
            <div />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input label="Start Date" type="date"
              value={form.startDate} onChange={(e) => setForm({ ...form, startDate: e.target.value })} />
            <Input label="End Date" type="date"
              value={form.endDate} onChange={(e) => setForm({ ...form, endDate: e.target.value })} />
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>Target Platforms</label>
            <div className="flex flex-wrap gap-2">
              {platformOptions.map((p) => {
                const selected = form.platforms.includes(p.key);
                return (
                  <button key={p.key} type="button"
                    onClick={() => setForm({
                      ...form,
                      platforms: selected ? form.platforms.filter((x) => x !== p.key) : [...form.platforms, p.key],
                    })}
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all cursor-pointer"
                    style={selected
                      ? { background: "rgba(124,58,237,0.18)", border: "1px solid rgba(124,58,237,0.40)", color: "#a78bfa" }
                      : { backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)", color: "var(--page-text-secondary)" }}
                  >
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: p.color }} />
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button variant="primary" icon={saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : formMode === "edit" ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              onClick={handleSubmit} disabled={saving}>
              {saving ? (formMode === "edit" ? "Saving…" : "Creating…") : formMode === "edit" ? "Save Changes" : "Create Campaign"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Add Posts Modal */}
      <Modal isOpen={showAddPosts} onClose={() => setShowAddPosts(false)} title="Add Posts to Campaign" size="lg">
        <div className="space-y-4">
          <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
            Select posts to link to <span className="font-medium" style={{ color: "var(--page-heading)" }}>{selectedCampaign?.name}</span>. Only posts not already in a campaign are shown.
          </p>

          {availableLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: "#7c3aed" }} />
            </div>
          ) : availablePosts.length > 0 ? (
            <div className="max-h-[50vh] space-y-2 overflow-y-auto pr-1">
              {availablePosts.map((p) => renderPostRow(p, { selectable: true }))}
            </div>
          ) : (
            <div className="rounded-xl p-8 text-center" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px dashed var(--surface-border)" }}>
              <FileText className="mx-auto mb-2 h-7 w-7" style={{ color: "var(--page-text-muted)", opacity: 0.5 }} />
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>No available posts</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--page-text-muted)" }}>Create posts on the Create Post page, then add them here.</p>
            </div>
          )}

          <div className="flex items-center justify-between gap-3 pt-1">
            <span className="text-xs tabular-nums" style={{ color: "var(--page-text-muted)" }}>{selectedPostIds.length} selected</span>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setShowAddPosts(false)}>Cancel</Button>
              <Button variant="primary" disabled={attaching || selectedPostIds.length === 0} onClick={attachPosts}
                icon={attaching ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}>
                {attaching ? "Adding…" : `Add ${selectedPostIds.length || ""} Post${selectedPostIds.length !== 1 ? "s" : ""}`}
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
