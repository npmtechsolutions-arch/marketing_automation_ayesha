import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Brain,
  Edit3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Video,
  Calendar,
  Hash,
  LayoutGrid,
  Zap,
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

const activeStrategy: Strategy = {
  id: 1,
  name: "Q1 2026 Growth Accelerator",
  goal: "Increase brand awareness and engagement by 40% across all platforms",
  confidence: 87,
  active: true,
  createdAt: "2026-01-15",
  updatedAt: "2026-03-28",
  platforms: [
    { name: "Instagram", percentage: 35, color: "#E4405F", postsPerWeek: 7, icon: Instagram },
    { name: "LinkedIn", percentage: 25, color: "#0A66C2", postsPerWeek: 5, icon: Linkedin },
    { name: "Twitter", percentage: 20, color: "#1DA1F2", postsPerWeek: 10, icon: Twitter },
    { name: "Facebook", percentage: 12, color: "#1877F2", postsPerWeek: 3, icon: Facebook },
    { name: "YouTube", percentage: 8, color: "#FF0000", postsPerWeek: 2, icon: Youtube },
  ],
  contentThemes: [
    "Product Updates",
    "Industry Insights",
    "Behind the Scenes",
    "User Testimonials",
    "Educational Content",
    "Trending Topics",
    "Team Culture",
    "Case Studies",
  ],
  aiReasoning:
    "Based on analysis of your audience demographics, engagement patterns, and competitor benchmarks, this strategy prioritizes Instagram and LinkedIn where your engagement rates are highest. The recommended posting frequency aligns with peak activity windows identified in your analytics. Video content is weighted heavily due to 3.2x higher engagement compared to static posts. Content themes are selected based on historical performance data showing these topics generate the most meaningful interactions with your target audience. The 35% Instagram allocation reflects the platform's dominance in visual content discovery for your industry vertical, while LinkedIn's 25% share leverages your growing professional authority.",
};

const strategyHistory: Strategy[] = [
  {
    id: 2,
    name: "Holiday Season Campaign",
    goal: "Maximize holiday engagement and conversions",
    confidence: 82,
    active: false,
    createdAt: "2025-11-01",
    updatedAt: "2025-12-31",
    platforms: [
      { name: "Instagram", percentage: 40, color: "#E4405F", postsPerWeek: 10, icon: Instagram },
      { name: "Facebook", percentage: 30, color: "#1877F2", postsPerWeek: 7, icon: Facebook },
      { name: "Twitter", percentage: 15, color: "#1DA1F2", postsPerWeek: 5, icon: Twitter },
      { name: "LinkedIn", percentage: 10, color: "#0A66C2", postsPerWeek: 2, icon: Linkedin },
      { name: "YouTube", percentage: 5, color: "#FF0000", postsPerWeek: 1, icon: Youtube },
    ],
    contentThemes: ["Holiday Promotions", "Gift Guides", "Year in Review", "Customer Stories"],
    aiReasoning: "Holiday-focused strategy with heavy emphasis on visual platforms for seasonal content.",
  },
  {
    id: 3,
    name: "Product Launch Strategy",
    goal: "Drive awareness for new product feature release",
    confidence: 91,
    active: false,
    createdAt: "2025-09-15",
    updatedAt: "2025-10-30",
    platforms: [
      { name: "LinkedIn", percentage: 35, color: "#0A66C2", postsPerWeek: 8, icon: Linkedin },
      { name: "Twitter", percentage: 30, color: "#1DA1F2", postsPerWeek: 12, icon: Twitter },
      { name: "Instagram", percentage: 20, color: "#E4405F", postsPerWeek: 5, icon: Instagram },
      { name: "YouTube", percentage: 10, color: "#FF0000", postsPerWeek: 2, icon: Youtube },
      { name: "Facebook", percentage: 5, color: "#1877F2", postsPerWeek: 2, icon: Facebook },
    ],
    contentThemes: ["Product Demo", "Feature Highlights", "User Benefits", "Technical Deep Dives"],
    aiReasoning: "B2B-focused launch strategy leveraging LinkedIn and Twitter for maximum professional reach.",
  },
  {
    id: 4,
    name: "Summer Brand Building",
    goal: "Build community engagement and brand loyalty",
    confidence: 76,
    active: false,
    createdAt: "2025-06-01",
    updatedAt: "2025-08-31",
    platforms: [
      { name: "Instagram", percentage: 45, color: "#E4405F", postsPerWeek: 8, icon: Instagram },
      { name: "Twitter", percentage: 25, color: "#1DA1F2", postsPerWeek: 7, icon: Twitter },
      { name: "Facebook", percentage: 15, color: "#1877F2", postsPerWeek: 4, icon: Facebook },
      { name: "LinkedIn", percentage: 10, color: "#0A66C2", postsPerWeek: 3, icon: Linkedin },
      { name: "YouTube", percentage: 5, color: "#FF0000", postsPerWeek: 1, icon: Youtube },
    ],
    contentThemes: ["Community Spotlights", "Summer Vibes", "Team Adventures", "User Generated Content"],
    aiReasoning: "Community-first approach prioritizing Instagram for visual storytelling and authentic engagement.",
  },
];

const recommendations = [
  {
    id: 1,
    icon: Video,
    title: "Increase video content on Instagram",
    description:
      "Your Reels get 3.2x more engagement than static posts. Aim for at least 60% video content on Instagram to maximize reach and follower growth.",
    impact: "+45% engagement",
    impactVariant: "success" as const,
    color: "text-pink-400",
    bg: "bg-pink-500/10",
    border: "border-pink-500/30",
  },
  {
    id: 2,
    icon: Calendar,
    title: "Post more on Tuesday/Thursday mornings",
    description:
      "Analytics show your audience peaks at 10-11 AM on Tuesdays and Thursdays. Shifting 3 posts per week to these slots could significantly boost visibility.",
    impact: "+28% reach",
    impactVariant: "success" as const,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  {
    id: 3,
    icon: Hash,
    title: "Engage with trending hashtags in your industry",
    description:
      "Posts using 3-5 niche industry hashtags get 22% more impressions than generic ones. Focus on #MarTech, #AIMarketing, and #ContentStrategy.",
    impact: "+22% impressions",
    impactVariant: "success" as const,
    color: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
  },
  {
    id: 4,
    icon: LayoutGrid,
    title: "Test carousel posts for higher engagement",
    description:
      "Carousel posts on LinkedIn and Instagram consistently outperform single-image posts by 2.1x. Try converting your top-performing content into carousels.",
    impact: "+2.1x engagement",
    impactVariant: "success" as const,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
];

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
          <GlassCard padding="lg" glow>
            <div className="flex flex-col lg:flex-row lg:items-start gap-6">
              {/* Left side: Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-3">
                  <Badge variant="success" dot>Active Strategy</Badge>
                  <span className="text-xs text-gray-500">
                    Updated {formatDate(activeStrategy.updatedAt)}
                  </span>
                </div>

                <h2 className="text-xl font-bold text-white mb-2">
                  {activeStrategy.name}
                </h2>
                <p className="text-sm text-gray-400 leading-relaxed mb-6">
                  {activeStrategy.goal}
                </p>

                {/* Platform Mix Bar */}
                <div className="mb-6">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Platform Mix
                  </p>
                  <div className="h-3 rounded-full overflow-hidden flex">
                    {activeStrategy.platforms.map((p) => (
                      <motion.div
                        key={p.name}
                        initial={{ width: 0 }}
                        animate={{ width: `${p.percentage}%` }}
                        transition={{ duration: 0.8, ease: "easeOut", delay: 0.3 }}
                        className="h-full first:rounded-l-full last:rounded-r-full"
                        style={{ backgroundColor: p.color }}
                        title={`${p.name}: ${p.percentage}%`}
                      />
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-3 mt-2">
                    {activeStrategy.platforms.map((p) => (
                      <div key={p.name} className="flex items-center gap-1.5 text-xs">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: p.color }}
                        />
                        <span className="text-gray-400">
                          {p.name} {p.percentage}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Posting Frequency Grid */}
                <div className="mb-6">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Posting Frequency
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                    {activeStrategy.platforms.map((p) => {
                      const Icon = p.icon;
                      return (
                        <div
                          key={p.name}
                          className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] text-center"
                        >
                          <div
                            className="w-8 h-8 rounded-lg flex items-center justify-center mx-auto mb-2"
                            style={{
                              backgroundColor: `${p.color}18`,
                              border: `1px solid ${p.color}30`,
                            }}
                          >
                            <Icon className="w-4 h-4" style={{ color: p.color }} />
                          </div>
                          <p className="text-sm font-semibold text-white">
                            {p.postsPerWeek}/wk
                          </p>
                          <p className="text-[10px] text-gray-500">{p.name}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Content Themes */}
                <div className="mb-6">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Content Themes
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {activeStrategy.contentThemes.map((theme) => (
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
                <div className="mb-4">
                  <button
                    onClick={() => setReasoningExpanded(!reasoningExpanded)}
                    className="flex items-center gap-2 text-xs font-medium text-gray-400 uppercase tracking-wider hover:text-white transition-colors"
                  >
                    <Brain className="w-3.5 h-3.5" />
                    AI Reasoning
                    {reasoningExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <AnimatePresence>
                    {reasoningExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="overflow-hidden"
                      >
                        <p className="text-sm text-gray-400 leading-relaxed mt-3 p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                          {activeStrategy.aiReasoning}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<Edit3 className="w-3.5 h-3.5" />}
                  >
                    Edit Strategy
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Apply Recommendations
                  </Button>
                </div>
              </div>

              {/* Right side: Confidence Score */}
              <div className="flex flex-col items-center gap-2 lg:pt-8">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Confidence
                </p>
                <CircularProgress value={activeStrategy.confidence} size={100} strokeWidth={7} />
                <p className="text-[10px] text-gray-500 mt-1">AI Score</p>
              </div>
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
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="lg" glow>
            <div className="flex items-center gap-2 mb-5">
              <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
                <Brain className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  AI Recommendations
                </h2>
                <p className="text-xs text-gray-500">
                  Suggestions to optimize your strategy
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {recommendations.map((rec, idx) => {
                const Icon = rec.icon;
                return (
                  <motion.div
                    key={rec.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + idx * 0.1 }}
                    className={cn(
                      "rounded-xl p-4 border-l-[3px] bg-white/[0.02] hover:bg-white/[0.04] transition-colors",
                      rec.border
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={cn(
                          "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
                          rec.bg
                        )}
                      >
                        <Icon className={cn("w-4 h-4", rec.color)} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white leading-snug">
                          {rec.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                          {rec.description}
                        </p>
                        <div className="flex items-center gap-3 mt-3">
                          <Badge variant={rec.impactVariant} size="sm">
                            {rec.impact}
                          </Badge>
                          <button className="text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1">
                            <Zap className="w-3 h-3" /> Apply
                          </button>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </GlassCard>
        </motion.div>
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
