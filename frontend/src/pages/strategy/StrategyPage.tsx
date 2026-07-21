import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Brain,
  Clock,
  CheckCircle2,
  ChevronRight,
  Zap,
  RefreshCw,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { formatDate } from "@/lib/utils";
import api, { getAccountId } from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";

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
interface Strategy {
  id: string;
  name: string;
  goal: string;
  confidence_score: number | null;
  is_active: boolean;
  created_at: string;
  platform_mix: Record<string, number> | null;
  posting_frequency: Record<string, number> | null;
  content_themes: string[] | null;
  reasoning: string | null;
}

interface Business {
  id: string;
  name: string;
  industry: string | null;
}

// ---------------------------------------------------------------------------
// Circular Progress Component
// ---------------------------------------------------------------------------
function CircularProgress({
  value,
  size = 80,
  strokeWidth = 6,
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#progressGradient)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        />
        <defs>
          <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-bold text-white">{value}%</span>
      </div>
    </div>
  );
}

// Platform color map
const platformColors: Record<string, string> = {
  instagram: "#E4405F",
  facebook: "#1877F2",
  twitter: "#1DA1F2",
  linkedin: "#0A66C2",
  tiktok: "#010101",
  youtube: "#FF0000",
};

// ---------------------------------------------------------------------------
// Platform Bar
// ---------------------------------------------------------------------------
function PlatformBar({ platformMix }: { platformMix: Record<string, number> }) {
  const total = Object.values(platformMix).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div>
      <div className="h-2.5 rounded-full overflow-hidden flex mb-2">
        {Object.entries(platformMix).map(([platform, weight]) => (
          <div
            key={platform}
            className="h-full first:rounded-l-full last:rounded-r-full"
            style={{
              backgroundColor: platformColors[platform] || "#6366F1",
              width: `${((weight / total) * 100).toFixed(1)}%`,
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {Object.entries(platformMix).map(([platform, weight]) => (
          <div key={platform} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: platformColors[platform] || "#6366F1" }}
            />
            <span className="text-slate-400 capitalize">
              {platform} ({((weight / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strategy Page
// ---------------------------------------------------------------------------
export default function StrategyPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  // Generate form state
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [selectedBusinessId, setSelectedBusinessId] = useState("");
  const [goal, setGoal] = useState("");
  const [budget, setBudget] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["instagram", "facebook"]);

  const accountId = localStorage.getItem("account_id");

  // ---------------------------------------------------------------------------
  // Fetch strategies
  // ---------------------------------------------------------------------------
  const fetchStrategies = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/strategies/`);
      const payload = res.data || res;
      const items = payload.items || payload.data?.items || [];
      setStrategies(items);
    } catch (err) {
      console.error("Failed to load strategies:", err);
      showError("Failed to load strategies");
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Fetch businesses for the generate modal
  // ---------------------------------------------------------------------------
  const fetchBusinesses = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      const res: any = await api.get(`/accounts/${activeAccountId}/businesses/`);
      const payload = res.data || res;
      const items: Business[] = payload.items || payload.data?.items || [];
      setBusinesses(items);
      if (items.length > 0) setSelectedBusinessId(items[0].id);
    } catch (err) {
      console.error("Failed to load businesses:", err);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  const openGenerateModal = () => {
    fetchBusinesses();
    setShowGenerateModal(true);
  };

  // ---------------------------------------------------------------------------
  // Generate strategy
  // ---------------------------------------------------------------------------
  const handleGenerate = async () => {
    if (!selectedBusinessId) {
      showError("Please select a business first");
      return;
    }
    if (!goal.trim()) {
      showError("Please enter a goal");
      return;
    }
    try {
      setGenerating(true);
      const payload: any = {
        business_id: selectedBusinessId,
        goal: goal.trim(),
        platforms: selectedPlatforms,
      };
      if (budget) payload.budget = parseFloat(budget);

      const res: any = await api.post(`/accounts/${accountId}/strategies/generate`, payload, { timeout: 90000 });
      const newStrategy: Strategy = res.data || res;
      setStrategies((prev) => [newStrategy, ...prev]);
      setShowGenerateModal(false);
      setGoal("");
      setBudget("");
      showSuccess("Strategy generated successfully!");
    } catch (err: any) {
      console.error("Failed to generate strategy:", err);
      showError(err?.response?.data?.detail || "Failed to generate strategy");
    } finally {
      setGenerating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Activate strategy
  // ---------------------------------------------------------------------------
  const handleActivate = async (strategyId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res: any = await api.post(`/accounts/${accountId}/strategies/${strategyId}/activate`);
      const updated: Strategy = res.data || res;
      setStrategies((prev) =>
        prev.map((s) => ({ ...s, is_active: s.id === strategyId ? updated.is_active : false }))
      );
      showSuccess("Strategy activated!");
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Failed to activate strategy");
    }
  };

  const activeStrategy = strategies.find((s) => s.is_active);
  const historyStrategies = strategies.filter((s) => !s.is_active);
  const confidencePct = activeStrategy?.confidence_score != null
    ? Math.round(activeStrategy.confidence_score * 100)
    : null;

  const allPlatforms = ["instagram", "facebook", "twitter", "linkedin", "youtube", "tiktok"];

  const togglePlatform = (p: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6 pb-8"
      >
        {/* Header */}
        <motion.div
          variants={fadeUp}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold text-white sm:text-3xl">Marketing Strategy</h1>
            <p className="mt-1 text-sm text-slate-400">
              AI-powered strategy recommendations for your brand
            </p>
          </div>
          <Button
            size="md"
            variant="primary"
            icon={<Sparkles className="w-4 h-4" />}
            onClick={openGenerateModal}
          >
            Generate New Strategy
          </Button>
        </motion.div>

        {/* Active Strategy Card */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg">
            {loading ? (
              <div className="flex items-center justify-center py-12 gap-3">
                <RefreshCw className="w-5 h-5 text-purple-400 animate-spin" />
                <span className="text-slate-400 text-sm">Loading strategies…</span>
              </div>
            ) : activeStrategy ? (
              <div className="space-y-5">
                {/* Active badge + name */}
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="success" size="sm" dot>Active</Badge>
                    </div>
                    <h2 className="text-lg font-semibold text-white">{activeStrategy.name}</h2>
                    <p className="text-sm text-slate-400 mt-0.5">{activeStrategy.goal}</p>
                  </div>
                  {confidencePct !== null && (
                    <div className="shrink-0 text-center">
                      <CircularProgress value={confidencePct} size={72} strokeWidth={5} />
                      <p className="text-[11px] text-slate-500 mt-1">Confidence</p>
                    </div>
                  )}
                </div>

                {/* Platform Mix */}
                {activeStrategy.platform_mix && Object.keys(activeStrategy.platform_mix).length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                      Platform Mix
                    </p>
                    <PlatformBar platformMix={activeStrategy.platform_mix} />
                  </div>
                )}

                {/* Content Themes */}
                {activeStrategy.content_themes && activeStrategy.content_themes.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                      Content Themes
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {activeStrategy.content_themes.map((theme) => (
                        <span
                          key={theme}
                          className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20"
                        >
                          {theme}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Reasoning */}
                {activeStrategy.reasoning && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                      AI Reasoning
                    </p>
                    <p className="text-sm text-slate-400 leading-relaxed p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                      {activeStrategy.reasoning}
                    </p>
                  </div>
                )}

                <p className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  Created {formatDate(activeStrategy.created_at)}
                </p>
              </div>
            ) : (
              <div className="text-center py-12">
                <Brain className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400 mb-2">No active strategy yet</p>
                <p className="text-sm text-slate-500 mb-5">
                  Generate a new strategy to get AI-powered recommendations
                </p>
                <Button
                  size="sm"
                  variant="primary"
                  icon={<Sparkles className="w-3.5 h-3.5" />}
                  onClick={openGenerateModal}
                >
                  Generate Strategy
                </Button>
              </div>
            )}
          </GlassCard>
        </motion.div>

        {/* Strategy History */}
        {!loading && historyStrategies.length > 0 && (
          <motion.div variants={fadeUp}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">Strategy History</h2>
              <p className="text-sm text-slate-400 mt-0.5">Past strategies — click to activate</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence>
                {historyStrategies.map((strategy, idx) => {
                  const pct = strategy.confidence_score != null
                    ? Math.round(strategy.confidence_score * 100)
                    : null;
                  return (
                    <motion.div
                      key={strategy.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: 0.05 + idx * 0.06 }}
                    >
                      <GlassCard
                        hover
                        padding="md"
                        onClick={() => setSelectedStrategy(strategy)}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <Badge variant="default" size="sm">Inactive</Badge>
                          {pct !== null && (
                            <div className="relative w-8 h-8">
                              <svg width={32} height={32} className="-rotate-90">
                                <circle cx={16} cy={16} r={12} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={3} />
                                <circle
                                  cx={16} cy={16} r={12} fill="none"
                                  stroke="#A855F7" strokeWidth={3} strokeLinecap="round"
                                  strokeDasharray={2 * Math.PI * 12}
                                  strokeDashoffset={2 * Math.PI * 12 - (pct / 100) * 2 * Math.PI * 12}
                                />
                              </svg>
                              <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-white">
                                {pct}
                              </span>
                            </div>
                          )}
                        </div>

                        <h3 className="text-sm font-semibold text-white mb-1 line-clamp-1">
                          {strategy.name}
                        </h3>
                        <p className="text-xs text-slate-500 mb-3 line-clamp-2">{strategy.goal}</p>

                        {strategy.platform_mix && Object.keys(strategy.platform_mix).length > 0 && (
                          <div className="h-1.5 rounded-full overflow-hidden flex mb-3">
                            {(() => {
                              const total = Object.values(strategy.platform_mix).reduce((a, b) => a + b, 0);
                              return Object.entries(strategy.platform_mix).map(([p, w]) => (
                                <div
                                  key={p}
                                  className="h-full"
                                  style={{
                                    backgroundColor: platformColors[p] || "#6366F1",
                                    width: `${((w / total) * 100).toFixed(1)}%`,
                                  }}
                                />
                              ));
                            })()}
                          </div>
                        )}

                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                            <Clock className="w-3 h-3" />
                            <span>{formatDate(strategy.created_at)}</span>
                          </div>
                          <button
                            onClick={(e) => handleActivate(strategy.id, e)}
                            className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                          >
                            Activate <ChevronRight className="w-3 h-3" />
                          </button>
                        </div>
                      </GlassCard>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}

        {/* Empty history state */}
        {!loading && strategies.length === 0 && (
          <motion.div variants={fadeUp}>
            <div className="text-center py-8 text-slate-500 text-sm">
              No strategies yet — generate your first one above!
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* ------------------------------------------------------------------- */}
      {/* Generate Strategy Modal                                             */}
      {/* ------------------------------------------------------------------- */}
      <Modal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        title="Generate New Strategy"
        size="md"
      >
        <div className="space-y-5">
          {/* Business selector */}
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">
              Business
            </label>
            {businesses.length === 0 ? (
              <p className="text-sm text-slate-500 italic">
                No businesses found. Add a business first.
              </p>
            ) : (
              <select
                value={selectedBusinessId}
                onChange={(e) => setSelectedBusinessId(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20"
              >
                {businesses.map((b) => (
                  <option key={b.id} value={b.id} className="bg-slate-900">
                    {b.name}{b.industry ? ` · ${b.industry}` : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Goal */}
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">
              Marketing Goal
            </label>
            <Input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Increase brand awareness by 30% in Q3"
            />
          </div>

          {/* Budget */}
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">
              Monthly Budget (USD) — optional
            </label>
            <Input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="e.g. 500"
            />
          </div>

          {/* Platforms */}
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
              Target Platforms
            </label>
            <div className="flex flex-wrap gap-2">
              {allPlatforms.map((p) => {
                const selected = selectedPlatforms.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => togglePlatform(p)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all border ${
                      selected
                        ? "bg-purple-500/20 text-purple-300 border-purple-500/40"
                        : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    {selected && <CheckCircle2 className="w-3 h-3 inline mr-1" />}
                    {p}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowGenerateModal(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={generating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              onClick={handleGenerate}
              disabled={generating || businesses.length === 0}
              className="flex-1"
            >
              {generating ? "Generating…" : "Generate Strategy"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ------------------------------------------------------------------- */}
      {/* Strategy Detail Modal                                               */}
      {/* ------------------------------------------------------------------- */}
      <Modal
        isOpen={!!selectedStrategy}
        onClose={() => setSelectedStrategy(null)}
        title={selectedStrategy?.name ?? "Strategy Details"}
        size="lg"
      >
        {selectedStrategy && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <Badge variant="default">Inactive</Badge>
              <span className="text-xs text-slate-500">
                {formatDate(selectedStrategy.created_at)}
              </span>
            </div>

            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Goal</p>
              <p className="text-sm text-slate-300">{selectedStrategy.goal}</p>
            </div>

            {selectedStrategy.confidence_score != null && (
              <div className="flex items-center gap-4">
                <div>
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
                    Confidence Score
                  </p>
                  <CircularProgress
                    value={Math.round(selectedStrategy.confidence_score * 100)}
                    size={72}
                    strokeWidth={5}
                  />
                </div>
              </div>
            )}

            {selectedStrategy.platform_mix && Object.keys(selectedStrategy.platform_mix).length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Platform Mix
                </p>
                <PlatformBar platformMix={selectedStrategy.platform_mix} />
              </div>
            )}

            {selectedStrategy.content_themes && selectedStrategy.content_themes.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Content Themes
                </p>
                <div className="flex flex-wrap gap-2">
                  {selectedStrategy.content_themes.map((theme) => (
                    <span
                      key={theme}
                      className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20"
                    >
                      {theme}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedStrategy.reasoning && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  AI Reasoning
                </p>
                <p className="text-sm text-slate-400 leading-relaxed p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  {selectedStrategy.reasoning}
                </p>
              </div>
            )}

            <div className="pt-2 flex gap-3">
              <Button
                variant="primary"
                size="sm"
                icon={<Zap className="w-3.5 h-3.5" />}
                onClick={(e) => {
                  handleActivate(selectedStrategy.id, e as any);
                  setSelectedStrategy(null);
                }}
              >
                Activate This Strategy
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedStrategy(null)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  );
}
