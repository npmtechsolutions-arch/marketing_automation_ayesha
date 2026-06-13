import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Brain,
  Clock,
} from "lucide-react";
import { Instagram, Linkedin, Twitter, Facebook, Youtube } from "@/components/shared/SocialIcons";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { cn, formatDate } from "@/lib/utils";

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
interface PlatformAllocation {
  name: string;
  percentage: number;
  color: string;
  postsPerWeek: number;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
}

interface Strategy {
  id: number;
  name: string;
  goal: string;
  confidence: number;
  active: boolean;
  createdAt: string;
  updatedAt: string;
  platforms: PlatformAllocation[];
  contentThemes: string[];
  aiReasoning: string;
}


const strategyHistory: Strategy[] = [];

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

// ---------------------------------------------------------------------------
// Strategy Page
// ---------------------------------------------------------------------------
export default function StrategyPage() {
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<Strategy | null>(null);

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
              Marketing Strategy
            </h1>
            <p className="mt-1 text-sm text-gray-400">
              AI-powered strategy recommendations for your brand
            </p>
          </div>

          <Button
            size="md"
            variant="primary"
            icon={<Sparkles className="w-4 h-4" />}
          >
            Generate New Strategy
          </Button>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Active Strategy Card */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg">
            <div className="text-center py-12">
              <Brain className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <p className="text-gray-400 mb-2">No active strategy yet</p>
              <p className="text-sm text-gray-500">Generate a new strategy to get AI-powered recommendations</p>
            </div>
          </GlassCard>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Strategy History */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-white">Strategy History</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Past strategies and their performance
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {strategyHistory.map((strategy, idx) => (
              <motion.div
                key={strategy.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + idx * 0.08 }}
              >
                <GlassCard
                  hover
                  padding="md"
                  onClick={() => setSelectedHistory(strategy)}
                >
                  <div className="flex items-center justify-between mb-3">
                    <Badge variant="default" size="sm">
                      Inactive
                    </Badge>
                    <div className="flex items-center gap-1.5">
                      <div className="relative w-8 h-8">
                        <svg width={32} height={32} className="-rotate-90">
                          <circle
                            cx={16}
                            cy={16}
                            r={12}
                            fill="none"
                            stroke="rgba(255,255,255,0.05)"
                            strokeWidth={3}
                          />
                          <circle
                            cx={16}
                            cy={16}
                            r={12}
                            fill="none"
                            stroke="#A855F7"
                            strokeWidth={3}
                            strokeLinecap="round"
                            strokeDasharray={2 * Math.PI * 12}
                            strokeDashoffset={
                              2 * Math.PI * 12 - (strategy.confidence / 100) * 2 * Math.PI * 12
                            }
                          />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-white">
                          {strategy.confidence}
                        </span>
                      </div>
                    </div>
                  </div>

                  <h3 className="text-sm font-semibold text-white mb-1 line-clamp-1">
                    {strategy.name}
                  </h3>
                  <p className="text-xs text-gray-500 mb-3 line-clamp-2">
                    {strategy.goal}
                  </p>

                  <div className="flex items-center gap-2 text-[11px] text-gray-500">
                    <Clock className="w-3 h-3" />
                    <span>
                      {formatDate(strategy.createdAt)} - {formatDate(strategy.updatedAt)}
                    </span>
                  </div>
                </GlassCard>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Recommendations Panel */}
      </motion.div>

      {/* ------------------------------------------------------------------- */}
      {/* Strategy History Detail Modal */}
      {/* ------------------------------------------------------------------- */}
      <Modal
        isOpen={!!selectedHistory}
        onClose={() => setSelectedHistory(null)}
        title={selectedHistory?.name ?? "Strategy Details"}
        size="lg"
      >
        {selectedHistory && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <Badge variant="default">Inactive</Badge>
              <span className="text-xs text-gray-500">
                {formatDate(selectedHistory.createdAt)} - {formatDate(selectedHistory.updatedAt)}
              </span>
            </div>

            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
                Goal
              </p>
              <p className="text-sm text-gray-300">{selectedHistory.goal}</p>
            </div>

            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
                  Confidence Score
                </p>
                <CircularProgress value={selectedHistory.confidence} size={72} strokeWidth={5} />
              </div>
            </div>

            {/* Platform Mix */}
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                Platform Mix
              </p>
              <div className="h-3 rounded-full overflow-hidden flex mb-2">
                {selectedHistory.platforms.map((p) => (
                  <div
                    key={p.name}
                    className="h-full first:rounded-l-full last:rounded-r-full"
                    style={{ backgroundColor: p.color, width: `${p.percentage}%` }}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                {selectedHistory.platforms.map((p) => (
                  <div key={p.name} className="flex items-center gap-1.5 text-xs">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: p.color }}
                    />
                    <span className="text-gray-400">
                      {p.name} {p.percentage}% ({p.postsPerWeek}/wk)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Content Themes */}
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                Content Themes
              </p>
              <div className="flex flex-wrap gap-2">
                {selectedHistory.contentThemes.map((theme) => (
                  <span
                    key={theme}
                    className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20"
                  >
                    {theme}
                  </span>
                ))}
              </div>
            </div>

            {/* AI Reasoning */}
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                AI Reasoning
              </p>
              <p className="text-sm text-gray-400 leading-relaxed p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                {selectedHistory.aiReasoning}
              </p>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  );
}
