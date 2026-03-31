import { useState, useRef, useCallback, type ChangeEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Upload,
  X,
  Hash,
  Image as ImageIcon,
  Camera,
  Wand2,
  Check,
  Plus,
  CalendarDays,
  Rocket,
  ArrowRight,
  ArrowLeft,
  Monitor,
  Tablet,
  Smartphone,
  RefreshCw,
  Edit3,
  CheckCircle2,
  Users,
  BadgeCheck,
  SunMedium,
  Contrast,
  Palette,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import PlatformIcon from "@/components/shared/PlatformIcon";
import DevicePreview from "@/components/shared/DevicePreview";
import { cn } from "@/lib/utils";

// ────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────
type Platform = "facebook" | "instagram" | "linkedin" | "twitter" | "youtube" | "tiktok" | "pinterest";
type Tone = "professional" | "casual" | "friendly" | "humorous" | "inspirational";
type MediaTab = "upload" | "ai-generate" | "photography";
type ImageStyle = "realistic" | "illustration" | "abstract" | "photography" | "3d-render";
type ImageSize = "square" | "portrait" | "landscape";
type PhotoTemplate = "product-shot" | "lifestyle" | "flat-lay" | "portrait" | "landscape-photo";
type DeviceType = "mobile" | "tablet" | "web";
type WizardStep = 1 | 2 | 3 | 4;

interface Account {
  id: string;
  platform: Platform;
  name: string;
  handle: string;
  verified: boolean;
  followers: number;
  avatar?: string;
}

// ────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────
const TONES: { key: Tone; label: string }[] = [
  { key: "professional", label: "Professional" },
  { key: "casual", label: "Casual" },
  { key: "friendly", label: "Friendly" },
  { key: "humorous", label: "Humorous" },
  { key: "inspirational", label: "Inspirational" },
];

const IMAGE_STYLES: { key: ImageStyle; label: string }[] = [
  { key: "realistic", label: "Realistic" },
  { key: "illustration", label: "Illustration" },
  { key: "abstract", label: "Abstract" },
  { key: "photography", label: "Photography" },
  { key: "3d-render", label: "3D Render" },
];

const IMAGE_SIZES: { key: ImageSize; label: string }[] = [
  { key: "square", label: "Square" },
  { key: "portrait", label: "Portrait" },
  { key: "landscape", label: "Landscape" },
];

const PHOTO_TEMPLATES: { key: PhotoTemplate; label: string }[] = [
  { key: "product-shot", label: "Product Shot" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "flat-lay", label: "Flat Lay" },
  { key: "portrait", label: "Portrait" },
  { key: "landscape-photo", label: "Landscape" },
];

const STEPS = [
  { step: 1 as WizardStep, label: "Create Content" },
  { step: 2 as WizardStep, label: "Select Accounts" },
  { step: 3 as WizardStep, label: "Preview" },
  { step: 4 as WizardStep, label: "Post / Schedule" },
];

// Mock accounts for demo
const MOCK_ACCOUNTS: Account[] = [
  { id: "1", platform: "facebook", name: "Acme Corp", handle: "@acmecorp", verified: true, followers: 24500 },
  { id: "2", platform: "facebook", name: "Acme Local", handle: "@acmelocal", verified: false, followers: 3200 },
  { id: "3", platform: "instagram", name: "Acme Visual", handle: "@acmevisual", verified: true, followers: 89000 },
  { id: "4", platform: "instagram", name: "Acme Lifestyle", handle: "@acmelife", verified: false, followers: 12400 },
  { id: "5", platform: "twitter", name: "Acme Corp", handle: "@acme", verified: true, followers: 45600 },
  { id: "6", platform: "twitter", name: "Acme Support", handle: "@acmesupport", verified: false, followers: 8900 },
  { id: "7", platform: "linkedin", name: "Acme Inc.", handle: "@acme-inc", verified: true, followers: 67800 },
  { id: "8", platform: "youtube", name: "Acme Channel", handle: "@acmechannel", verified: true, followers: 120000 },
  { id: "9", platform: "tiktok", name: "Acme Trends", handle: "@acmetrends", verified: false, followers: 34500 },
  { id: "10", platform: "pinterest", name: "Acme Pins", handle: "@acmepins", verified: false, followers: 5600 },
];

function formatFollowers(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toString();
}

// ────────────────────────────────────────────────────────
// Step transition variants
// ────────────────────────────────────────────────────────
const stepVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 60 : -60,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -60 : 60,
    opacity: 0,
  }),
};

// ────────────────────────────────────────────────────────
// Shimmer loading animation
// ────────────────────────────────────────────────────────
function ShimmerBlock({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-white/5", className)}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </div>
  );
}

// ────────────────────────────────────────────────────────
// Main Page Component
// ────────────────────────────────────────────────────────
export default function CreatePostPage() {
  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [direction, setDirection] = useState(1);

  // Step 1 - Content
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [selectedTone, setSelectedTone] = useState<Tone>("professional");
  const [isGeneratingContent, setIsGeneratingContent] = useState(false);
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [hashtagInput, setHashtagInput] = useState("");

  // Media
  const [mediaTab, setMediaTab] = useState<MediaTab>("upload");
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);
  const [aiImagePrompt, setAiImagePrompt] = useState("");
  const [imageStyle, setImageStyle] = useState<ImageStyle>("realistic");
  const [imageSize, setImageSize] = useState<ImageSize>("square");
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [generatedImages, setGeneratedImages] = useState<string[]>([]);
  const [photoTemplate, setPhotoTemplate] = useState<PhotoTemplate>("product-shot");
  const [brightness, setBrightness] = useState(50);
  const [contrast, setContrast] = useState(50);
  const [saturation, setSaturation] = useState(50);

  // Step 2 - Accounts
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);

  // Step 3 - Preview
  const [previewDevice, setPreviewDevice] = useState<DeviceType>("mobile");

  // Step 4 - Schedule
  const [postMode, setPostMode] = useState<"now" | "schedule">("now");
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [isPosting, setIsPosting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Navigation ──
  const goToStep = useCallback(
    (step: WizardStep) => {
      setDirection(step > currentStep ? 1 : -1);
      setCurrentStep(step);
    },
    [currentStep]
  );

  const nextStep = useCallback(() => {
    if (currentStep < 4) goToStep((currentStep + 1) as WizardStep);
  }, [currentStep, goToStep]);

  const prevStep = useCallback(() => {
    if (currentStep > 1) goToStep((currentStep - 1) as WizardStep);
  }, [currentStep, goToStep]);

  // ── Handlers ──
  const handleGenerateContent = useCallback(() => {
    if (!aiPrompt.trim()) return;
    setIsGeneratingContent(true);
    setTimeout(() => {
      setContent(
        `Here's an engaging post about "${aiPrompt.trim()}":\n\nWe're thrilled to share something special with our community. This is what drives us forward every day - the passion to create, innovate, and deliver value.\n\nWhat do you think? Let us know in the comments below!`
      );
      setIsGeneratingContent(false);
    }, 2000);
  }, [aiPrompt]);

  const handleAiSuggestHashtags = useCallback(() => {
    const suggestions = ["marketing", "digitalstrategy", "socialmedia", "growthhacking", "branding", "contentcreation"];
    setHashtags((prev) => {
      const newTags = suggestions.filter((s) => !prev.includes(s));
      return [...prev, ...newTags.slice(0, 4)];
    });
  }, []);

  const addHashtag = useCallback(() => {
    const tag = hashtagInput.trim().replace(/^#/, "");
    if (tag && !hashtags.includes(tag)) {
      setHashtags((prev) => [...prev, tag]);
      setHashtagInput("");
    }
  }, [hashtagInput, hashtags]);

  const removeHashtag = useCallback((tag: string) => {
    setHashtags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const handleFileUpload = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        setUploadedImages((prev) => [...prev, reader.result as string]);
      };
      reader.readAsDataURL(file);
    });
    e.target.value = "";
  }, []);

  const handleGenerateImage = useCallback(() => {
    if (!aiImagePrompt.trim()) return;
    setIsGeneratingImage(true);
    setTimeout(() => {
      // Placeholder generated images
      setGeneratedImages([
        "generated-1",
        "generated-2",
        "generated-3",
        "generated-4",
      ]);
      setIsGeneratingImage(false);
    }, 2500);
  }, [aiImagePrompt]);

  const toggleAccount = useCallback((id: string) => {
    setSelectedAccounts((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  }, []);

  const togglePlatformAll = useCallback(
    (platform: Platform) => {
      const platformAccounts = MOCK_ACCOUNTS.filter((a) => a.platform === platform);
      const allSelected = platformAccounts.every((a) => selectedAccounts.includes(a.id));
      if (allSelected) {
        setSelectedAccounts((prev) => prev.filter((id) => !platformAccounts.find((a) => a.id === id)));
      } else {
        setSelectedAccounts((prev) => {
          const newIds = platformAccounts.map((a) => a.id).filter((id) => !prev.includes(id));
          return [...prev, ...newIds];
        });
      }
    },
    [selectedAccounts]
  );

  const allImages = [...uploadedImages, ...generatedImages.filter((g) => uploadedImages.includes(g) || g.startsWith("generated-"))];

  const handleConfirmPost = useCallback(() => {
    setIsPosting(true);
    setTimeout(() => {
      setIsPosting(false);
      // Would navigate away or show success
    }, 2000);
  }, []);

  // Group accounts by platform
  const accountsByPlatform = MOCK_ACCOUNTS.reduce(
    (acc, account) => {
      if (!acc[account.platform]) acc[account.platform] = [];
      acc[account.platform].push(account);
      return acc;
    },
    {} as Record<Platform, Account[]>
  );

  const selectedPlatformCount = new Set(
    MOCK_ACCOUNTS.filter((a) => selectedAccounts.includes(a.id)).map((a) => a.platform)
  ).size;

  // ────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────
  return (
    <DashboardLayout>
      {/* Shimmer keyframe (injected once) */}
      <style>{`@keyframes shimmer{100%{transform:translateX(100%)}}`}</style>

      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Page Header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Create Post</h1>
            <p className="text-sm text-gray-400 mt-1">
              Craft, preview, and publish content across all your accounts
            </p>
          </div>
        </div>

        {/* ── Progress Bar ── */}
        <GlassCard padding="sm" className="!bg-white/[0.03]">
          <div className="flex items-center justify-between px-2">
            {STEPS.map((s, i) => {
              const isActive = currentStep === s.step;
              const isComplete = currentStep > s.step;
              return (
                <div key={s.step} className="flex items-center flex-1 last:flex-initial">
                  <button
                    onClick={() => {
                      if (isComplete) goToStep(s.step);
                    }}
                    disabled={!isComplete && !isActive}
                    className={cn(
                      "flex items-center gap-2.5 transition-all duration-300",
                      isComplete && "cursor-pointer",
                      !isComplete && !isActive && "cursor-default"
                    )}
                  >
                    <div
                      className={cn(
                        "w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold transition-all duration-300 flex-shrink-0",
                        isActive &&
                          "bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/30",
                        isComplete &&
                          "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
                        !isActive &&
                          !isComplete &&
                          "bg-white/5 text-gray-500 border border-white/10"
                      )}
                    >
                      {isComplete ? <Check className="w-4 h-4" /> : s.step}
                    </div>
                    <span
                      className={cn(
                        "text-sm font-medium hidden sm:block transition-colors",
                        isActive && "text-white",
                        isComplete && "text-emerald-400",
                        !isActive && !isComplete && "text-gray-500"
                      )}
                    >
                      {s.label}
                    </span>
                  </button>
                  {i < STEPS.length - 1 && (
                    <div className="flex-1 mx-3 h-px">
                      <div
                        className={cn(
                          "h-full transition-colors duration-300",
                          currentStep > s.step
                            ? "bg-emerald-500/40"
                            : "bg-white/10"
                        )}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </GlassCard>

        {/* ── Step Content ── */}
        <AnimatePresence mode="wait" custom={direction}>
          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 1: Create Content                         */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 1 && (
            <motion.div
              key="step1"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="grid grid-cols-1 lg:grid-cols-5 gap-6"
            >
              {/* Left Panel (60%) */}
              <div className="lg:col-span-3 space-y-5">
                {/* Title */}
                <GlassCard>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Post title - optional"
                    className="w-full bg-transparent text-white text-lg font-medium placeholder-gray-500 outline-none"
                  />
                </GlassCard>

                {/* AI Content Generator */}
                <div className="relative rounded-2xl p-[1px] bg-gradient-to-r from-purple-600/60 via-blue-500/40 to-purple-600/60">
                  <div className="rounded-2xl bg-slate-950/90 backdrop-blur-xl p-5 space-y-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>
                      <h3 className="text-sm font-semibold text-white">
                        Generate with AI
                      </h3>
                      <Badge variant="info" size="sm">Beta</Badge>
                    </div>

                    <textarea
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="Describe what you want to post about..."
                      rows={3}
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />

                    {/* Tone pills */}
                    <div>
                      <p className="text-xs text-gray-400 mb-2">Tone</p>
                      <div className="flex flex-wrap gap-2">
                        {TONES.map((tone) => (
                          <button
                            key={tone.key}
                            onClick={() => setSelectedTone(tone.key)}
                            className={cn(
                              "px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border",
                              selectedTone === tone.key
                                ? "bg-purple-500/20 border-purple-500/40 text-purple-300 shadow-sm shadow-purple-500/10"
                                : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:text-gray-300"
                            )}
                          >
                            {tone.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <Button
                      onClick={handleGenerateContent}
                      loading={isGeneratingContent}
                      disabled={!aiPrompt.trim()}
                      icon={<Sparkles className="w-4 h-4" />}
                      className="w-full"
                    >
                      Generate Content
                    </Button>

                    {/* Shimmer loading state */}
                    {isGeneratingContent && (
                      <div className="space-y-2 pt-2">
                        <ShimmerBlock className="h-4 w-full" />
                        <ShimmerBlock className="h-4 w-4/5" />
                        <ShimmerBlock className="h-4 w-3/5" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Content textarea */}
                <GlassCard>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-gray-300">
                        Content
                      </label>
                      <span
                        className={cn(
                          "text-xs",
                          content.length > 2200 ? "text-red-400" : "text-gray-500"
                        )}
                      >
                        {content.length} / 2,200
                      </span>
                    </div>
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder="Write your post content here..."
                      className="w-full min-h-[250px] bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-y focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />
                  </div>
                </GlassCard>

                {/* Hashtag Manager */}
                <GlassCard>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Hash className="w-4 h-4 text-purple-400" />
                      <h3 className="text-sm font-medium text-gray-300">
                        Hashtags
                      </h3>
                    </div>

                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={hashtagInput}
                        onChange={(e) => setHashtagInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && addHashtag()}
                        placeholder="Add a hashtag..."
                        className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 outline-none focus:border-purple-500/50 transition-all"
                      />
                      <Button size="md" variant="secondary" onClick={addHashtag}>
                        <Plus className="w-4 h-4" />
                      </Button>
                      <Button
                        size="md"
                        variant="ghost"
                        onClick={handleAiSuggestHashtags}
                        icon={<Sparkles className="w-3.5 h-3.5" />}
                      >
                        AI Suggest
                      </Button>
                    </div>

                    {hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {hashtags.map((tag) => (
                          <motion.span
                            key={tag}
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium"
                          >
                            #{tag}
                            <button
                              onClick={() => removeHashtag(tag)}
                              className="ml-0.5 hover:text-blue-200 transition-colors"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </motion.span>
                        ))}
                      </div>
                    )}
                  </div>
                </GlassCard>
              </div>

              {/* Right Panel (40%) */}
              <div className="lg:col-span-2 space-y-5">
                {/* Image & Media Section */}
                <GlassCard className="!p-0 overflow-hidden">
                  {/* Tab bar */}
                  <div className="flex border-b border-white/10">
                    {(
                      [
                        { key: "upload" as MediaTab, label: "Upload", icon: <Upload className="w-3.5 h-3.5" /> },
                        { key: "ai-generate" as MediaTab, label: "AI Generate", icon: <Wand2 className="w-3.5 h-3.5" /> },
                        { key: "photography" as MediaTab, label: "Photography", icon: <Camera className="w-3.5 h-3.5" /> },
                      ] as const
                    ).map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setMediaTab(tab.key)}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-1.5 px-3 py-3 text-xs font-medium transition-all duration-200 border-b-2",
                          mediaTab === tab.key
                            ? "border-purple-500 text-purple-300 bg-purple-500/5"
                            : "border-transparent text-gray-500 hover:text-gray-300 hover:bg-white/5"
                        )}
                      >
                        {tab.icon}
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <div className="p-4">
                    {/* Upload Tab */}
                    {mediaTab === "upload" && (
                      <div className="space-y-4">
                        {/* Drag & drop zone */}
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full border-2 border-dashed border-white/10 rounded-xl p-8 flex flex-col items-center gap-3 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all duration-200 group"
                        >
                          <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center group-hover:bg-purple-500/10 transition-colors">
                            <Upload className="w-5 h-5 text-gray-400 group-hover:text-purple-400 transition-colors" />
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-gray-300">
                              Drag & drop or click to upload
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              PNG, JPG, GIF up to 10MB
                            </p>
                          </div>
                        </button>
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={handleFileUpload}
                          className="hidden"
                        />

                        {/* Image preview grid */}
                        {uploadedImages.length > 0 && (
                          <div className="grid grid-cols-2 gap-2">
                            {uploadedImages.map((img, i) => (
                              <div
                                key={i}
                                className="relative rounded-xl overflow-hidden border border-white/10 aspect-square group"
                              >
                                <img
                                  src={img}
                                  alt={`Upload ${i + 1}`}
                                  className="w-full h-full object-cover"
                                />
                                <button
                                  onClick={() =>
                                    setUploadedImages((prev) =>
                                      prev.filter((_, idx) => idx !== i)
                                    )
                                  }
                                  className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/70 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* AI Generate Tab */}
                    {mediaTab === "ai-generate" && (
                      <div className="space-y-4">
                        <textarea
                          value={aiImagePrompt}
                          onChange={(e) => setAiImagePrompt(e.target.value)}
                          placeholder="Describe the image you want to generate..."
                          rows={3}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                        />

                        {/* Style selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Style</p>
                          <div className="flex flex-wrap gap-1.5">
                            {IMAGE_STYLES.map((s) => (
                              <button
                                key={s.key}
                                onClick={() => setImageStyle(s.key)}
                                className={cn(
                                  "px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all border",
                                  imageStyle === s.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {s.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Size selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Size</p>
                          <div className="flex gap-2">
                            {IMAGE_SIZES.map((s) => (
                              <button
                                key={s.key}
                                onClick={() => setImageSize(s.key)}
                                className={cn(
                                  "flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-all border text-center",
                                  imageSize === s.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {s.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        <Button
                          onClick={handleGenerateImage}
                          loading={isGeneratingImage}
                          disabled={!aiImagePrompt.trim()}
                          icon={<Wand2 className="w-4 h-4" />}
                          className="w-full"
                        >
                          Generate Image
                        </Button>

                        {/* Generated images */}
                        {isGeneratingImage && (
                          <div className="grid grid-cols-2 gap-2">
                            {[1, 2, 3, 4].map((i) => (
                              <ShimmerBlock key={i} className="aspect-square rounded-xl" />
                            ))}
                          </div>
                        )}

                        {!isGeneratingImage && generatedImages.length > 0 && (
                          <div className="grid grid-cols-2 gap-2">
                            {generatedImages.map((img, i) => (
                              <div
                                key={i}
                                className="relative rounded-xl overflow-hidden border border-white/10 aspect-square bg-gradient-to-br from-purple-900/30 to-blue-900/30 flex flex-col items-center justify-center group"
                              >
                                <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center mb-2">
                                  <ImageIcon className="w-5 h-5 text-gray-500" />
                                </div>
                                <span className="text-[10px] text-gray-500">
                                  Generated {i + 1}
                                </span>
                                <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button
                                    onClick={() =>
                                      setUploadedImages((prev) => [...prev, img])
                                    }
                                    className="px-2.5 py-1 rounded-lg bg-purple-500/80 text-white text-[10px] font-medium hover:bg-purple-500 transition-colors"
                                  >
                                    Use This
                                  </button>
                                  <button
                                    onClick={handleGenerateImage}
                                    className="px-2.5 py-1 rounded-lg bg-white/10 text-white text-[10px] font-medium hover:bg-white/20 transition-colors"
                                  >
                                    Redo
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Digital Photography Tab */}
                    {mediaTab === "photography" && (
                      <div className="space-y-4">
                        <p className="text-xs text-gray-400">
                          Create digital photography from your content
                        </p>

                        {/* Template selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Template</p>
                          <div className="grid grid-cols-2 gap-1.5">
                            {PHOTO_TEMPLATES.map((t) => (
                              <button
                                key={t.key}
                                onClick={() => setPhotoTemplate(t.key)}
                                className={cn(
                                  "px-2.5 py-2 rounded-lg text-[11px] font-medium transition-all border text-center",
                                  photoTemplate === t.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {t.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Filter controls */}
                        <div className="space-y-3">
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <SunMedium className="w-3 h-3" /> Brightness
                              </span>
                              <span className="text-[10px] text-gray-500">{brightness}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={brightness}
                              onChange={(e) => setBrightness(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <Contrast className="w-3 h-3" /> Contrast
                              </span>
                              <span className="text-[10px] text-gray-500">{contrast}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={contrast}
                              onChange={(e) => setContrast(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <Palette className="w-3 h-3" /> Saturation
                              </span>
                              <span className="text-[10px] text-gray-500">{saturation}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={saturation}
                              onChange={(e) => setSaturation(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                        </div>

                        {/* Color overlay */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Color Overlay</p>
                          <div className="flex gap-2">
                            {[
                              "bg-transparent border border-white/20",
                              "bg-purple-500/40",
                              "bg-blue-500/40",
                              "bg-amber-500/40",
                              "bg-rose-500/40",
                              "bg-emerald-500/40",
                              "bg-slate-800/60",
                            ].map((color, i) => (
                              <button
                                key={i}
                                className={cn(
                                  "w-7 h-7 rounded-lg transition-all hover:scale-110",
                                  color
                                )}
                              />
                            ))}
                          </div>
                        </div>

                        {/* Preview area */}
                        <div className="aspect-video rounded-xl bg-gradient-to-br from-purple-900/20 to-blue-900/20 border border-white/5 flex items-center justify-center"
                          style={{
                            filter: `brightness(${brightness / 50}) contrast(${contrast / 50}) saturate(${saturation / 50})`,
                          }}
                        >
                          <div className="text-center">
                            <Camera className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                            <p className="text-xs text-gray-500">
                              Photography Preview
                            </p>
                          </div>
                        </div>

                        <Button variant="primary" className="w-full">
                          Apply
                        </Button>
                      </div>
                    )}
                  </div>
                </GlassCard>

                {/* Next button */}
                <Button
                  onClick={nextStep}
                  size="lg"
                  fullWidth
                  icon={<ArrowRight className="w-4 h-4" />}
                  iconPosition="right"
                  disabled={!content.trim()}
                >
                  Next: Select Accounts
                </Button>
              </div>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 2: Select Target Accounts                 */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 2 && (
            <motion.div
              key="step2"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              <div className="text-center mb-2">
                <h2 className="text-xl font-bold text-white">
                  Where should this post go?
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Select the accounts you want to publish to
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {(Object.entries(accountsByPlatform) as [Platform, Account[]][]).map(
                  ([platform, accounts]) => {
                    const allSelected = accounts.every((a) =>
                      selectedAccounts.includes(a.id)
                    );
                    return (
                      <GlassCard key={platform}>
                        {/* Platform header */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2.5">
                            <PlatformIcon platform={platform} size="md" showLabel />
                          </div>
                          <label className="flex items-center gap-2 cursor-pointer group">
                            <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors">
                              Select All
                            </span>
                            <button
                              onClick={() => togglePlatformAll(platform)}
                              className={cn(
                                "w-5 h-5 rounded-md flex items-center justify-center transition-all duration-200 border",
                                allSelected
                                  ? "bg-purple-500 border-purple-500 text-white"
                                  : "bg-white/5 border-white/20 hover:border-purple-500/50"
                              )}
                            >
                              {allSelected && <Check className="w-3 h-3" />}
                            </button>
                          </label>
                        </div>

                        {/* Account list */}
                        <div className="space-y-2">
                          {accounts.map((account) => {
                            const isSelected = selectedAccounts.includes(account.id);
                            return (
                              <button
                                key={account.id}
                                onClick={() => toggleAccount(account.id)}
                                className={cn(
                                  "w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 border text-left",
                                  isSelected
                                    ? "bg-purple-500/10 border-purple-500/30 shadow-sm shadow-purple-500/5"
                                    : "bg-white/[0.02] border-white/5 hover:bg-white/5 hover:border-white/10"
                                )}
                              >
                                {/* Avatar */}
                                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500/30 to-blue-500/30 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white/60">
                                  {account.name.charAt(0)}
                                </div>

                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-medium text-white truncate">
                                      {account.name}
                                    </span>
                                    {account.verified && (
                                      <BadgeCheck className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-gray-500 truncate">
                                      {account.handle}
                                    </span>
                                    <span className="text-[10px] text-gray-600">
                                      {formatFollowers(account.followers)} followers
                                    </span>
                                  </div>
                                </div>

                                {/* Checkbox */}
                                <div
                                  className={cn(
                                    "w-5 h-5 rounded-md flex items-center justify-center transition-all duration-200 border flex-shrink-0",
                                    isSelected
                                      ? "bg-purple-500 border-purple-500 text-white"
                                      : "bg-white/5 border-white/20"
                                  )}
                                >
                                  {isSelected && <Check className="w-3 h-3" />}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </GlassCard>
                    );
                  }
                )}
              </div>

              {/* Summary bar */}
              <GlassCard
                padding="sm"
                glow={selectedAccounts.length > 0}
                className="!bg-white/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-gray-300">
                      {selectedAccounts.length > 0 ? (
                        <>
                          <span className="font-semibold text-white">
                            {selectedAccounts.length}
                          </span>{" "}
                          account{selectedAccounts.length !== 1 && "s"} selected
                          across{" "}
                          <span className="font-semibold text-white">
                            {selectedPlatformCount}
                          </span>{" "}
                          platform{selectedPlatformCount !== 1 && "s"}
                        </>
                      ) : (
                        "No accounts selected"
                      )}
                    </span>
                  </div>
                </div>
              </GlassCard>

              {/* Navigation */}
              <div className="flex gap-3">
                <Button variant="secondary" onClick={prevStep} icon={<ArrowLeft className="w-4 h-4" />} size="lg">
                  Back
                </Button>
                <Button
                  onClick={nextStep}
                  size="lg"
                  fullWidth
                  icon={<ArrowRight className="w-4 h-4" />}
                  iconPosition="right"
                  disabled={selectedAccounts.length === 0}
                >
                  Next: Preview
                </Button>
              </div>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 3: Multi-Device Preview                   */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 3 && (
            <motion.div
              key="step3"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              {/* Device tab bar */}
              <GlassCard padding="sm" className="!bg-white/[0.03]">
                <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
                  {(
                    [
                      { key: "mobile" as DeviceType, label: "Mobile", icon: <Smartphone className="w-4 h-4" /> },
                      { key: "tablet" as DeviceType, label: "Tablet", icon: <Tablet className="w-4 h-4" /> },
                      { key: "web" as DeviceType, label: "Web", icon: <Monitor className="w-4 h-4" /> },
                    ] as const
                  ).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setPreviewDevice(tab.key)}
                      className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 flex-1",
                        previewDevice === tab.key
                          ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20 shadow-lg shadow-purple-500/5"
                          : "text-gray-400 hover:text-white"
                      )}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  ))}
                </div>
              </GlassCard>

              {/* Device frame */}
              <div className="flex justify-center py-4">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={previewDevice}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.25 }}
                    className={cn(
                      "w-full",
                      previewDevice === "mobile" && "max-w-[280px]",
                      previewDevice === "tablet" && "max-w-[620px]",
                      previewDevice === "web" && "max-w-[960px]"
                    )}
                  >
                    <DevicePreview
                      content={content}
                      images={allImages}
                      hashtags={hashtags}
                      device={previewDevice}
                      platformName={
                        MOCK_ACCOUNTS.find((a) => selectedAccounts.includes(a.id))
                          ?.platform ?? "Social Feed"
                      }
                    />
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Satisfied section */}
              <GlassCard>
                <div className="text-center space-y-4">
                  <h3 className="text-lg font-semibold text-white">
                    Satisfied with the preview?
                  </h3>
                  <p className="text-sm text-gray-400">
                    You can go back to edit or regenerate content, or proceed to publish.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <Button
                      variant="ghost"
                      onClick={() => goToStep(1)}
                      icon={<RefreshCw className="w-4 h-4" />}
                    >
                      Regenerate Content
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => goToStep(1)}
                      icon={<Edit3 className="w-4 h-4" />}
                    >
                      Edit Content
                    </Button>
                    <Button
                      onClick={nextStep}
                      icon={<CheckCircle2 className="w-4 h-4" />}
                      iconPosition="right"
                    >
                      Looks Good!
                    </Button>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 4: Post / Schedule                        */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 4 && (
            <motion.div
              key="step4"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              {/* Summary card */}
              <GlassCard>
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                  Summary
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Content preview */}
                  <div className="md:col-span-2 space-y-3">
                    {title && (
                      <p className="text-base font-semibold text-white">{title}</p>
                    )}
                    <p className="text-sm text-gray-300 whitespace-pre-wrap line-clamp-4">
                      {content}
                    </p>
                    {hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {hashtags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs text-blue-400 font-medium"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    {allImages.length > 0 && (
                      <div className="flex gap-2 mt-2">
                        {allImages.slice(0, 4).map((img, i) => (
                          <div
                            key={i}
                            className="w-14 h-14 rounded-lg bg-gradient-to-br from-purple-900/30 to-blue-900/30 border border-white/10 flex items-center justify-center overflow-hidden"
                          >
                            {img.startsWith("data:") || img.startsWith("http") || img.startsWith("blob:") ? (
                              <img src={img} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <ImageIcon className="w-4 h-4 text-gray-500" />
                            )}
                          </div>
                        ))}
                        {allImages.length > 4 && (
                          <div className="w-14 h-14 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-xs text-gray-400 font-medium">
                            +{allImages.length - 4}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Target accounts */}
                  <div>
                    <p className="text-xs text-gray-400 mb-2">Publishing to</p>
                    <div className="space-y-1.5">
                      {MOCK_ACCOUNTS.filter((a) =>
                        selectedAccounts.includes(a.id)
                      ).map((account) => (
                        <div
                          key={account.id}
                          className="flex items-center gap-2 text-xs"
                        >
                          <PlatformIcon platform={account.platform} size="sm" />
                          <span className="text-gray-300 truncate">
                            {account.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </GlassCard>

              {/* Post options */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Post Now */}
                <button
                  onClick={() => setPostMode("now")}
                  className={cn(
                    "text-left rounded-2xl p-6 transition-all duration-300 border-2 group",
                    postMode === "now"
                      ? "bg-gradient-to-br from-purple-600/10 to-blue-600/10 border-purple-500/40 shadow-lg shadow-purple-500/10"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        "w-14 h-14 rounded-2xl flex items-center justify-center transition-all flex-shrink-0",
                        postMode === "now"
                          ? "bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                          : "bg-white/5 group-hover:bg-white/10"
                      )}
                    >
                      <Rocket
                        className={cn(
                          "w-6 h-6 transition-colors",
                          postMode === "now" ? "text-white" : "text-gray-400"
                        )}
                      />
                    </div>
                    <div>
                      <h3
                        className={cn(
                          "text-lg font-semibold transition-colors",
                          postMode === "now" ? "text-white" : "text-gray-300"
                        )}
                      >
                        Post Now
                      </h3>
                      <p className="text-sm text-gray-400 mt-1">
                        Publish to {selectedAccounts.length} account
                        {selectedAccounts.length !== 1 && "s"} immediately
                      </p>
                    </div>
                  </div>
                  {postMode === "now" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="mt-4 pt-4 border-t border-purple-500/20"
                    >
                      <p className="text-xs text-purple-300">
                        Your post will be published across all selected accounts within seconds.
                      </p>
                    </motion.div>
                  )}
                </button>

                {/* Schedule */}
                <button
                  onClick={() => setPostMode("schedule")}
                  className={cn(
                    "text-left rounded-2xl p-6 transition-all duration-300 border-2 group",
                    postMode === "schedule"
                      ? "bg-gradient-to-br from-purple-600/10 to-blue-600/10 border-purple-500/40 shadow-lg shadow-purple-500/10"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        "w-14 h-14 rounded-2xl flex items-center justify-center transition-all flex-shrink-0",
                        postMode === "schedule"
                          ? "bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                          : "bg-white/5 group-hover:bg-white/10"
                      )}
                    >
                      <CalendarDays
                        className={cn(
                          "w-6 h-6 transition-colors",
                          postMode === "schedule" ? "text-white" : "text-gray-400"
                        )}
                      />
                    </div>
                    <div>
                      <h3
                        className={cn(
                          "text-lg font-semibold transition-colors",
                          postMode === "schedule" ? "text-white" : "text-gray-300"
                        )}
                      >
                        Schedule
                      </h3>
                      <p className="text-sm text-gray-400 mt-1">
                        Schedule for later
                      </p>
                    </div>
                  </div>
                  {postMode === "schedule" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="mt-4 pt-4 border-t border-purple-500/20"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] text-gray-400 mb-1">
                            Date
                          </label>
                          <input
                            type="date"
                            value={scheduleDate}
                            onChange={(e) => setScheduleDate(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 transition-all [color-scheme:dark]"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-gray-400 mb-1">
                            Time
                          </label>
                          <input
                            type="time"
                            value={scheduleTime}
                            onChange={(e) => setScheduleTime(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 transition-all [color-scheme:dark]"
                          />
                        </div>
                      </div>
                    </motion.div>
                  )}
                </button>
              </div>

              {/* Navigation */}
              <div className="flex gap-3">
                <Button variant="secondary" onClick={prevStep} icon={<ArrowLeft className="w-4 h-4" />} size="lg">
                  Back
                </Button>
                <Button
                  onClick={handleConfirmPost}
                  loading={isPosting}
                  size="lg"
                  fullWidth
                  disabled={
                    postMode === "schedule" && (!scheduleDate || !scheduleTime)
                  }
                  icon={
                    postMode === "now" ? (
                      <Rocket className="w-4 h-4" />
                    ) : (
                      <CalendarDays className="w-4 h-4" />
                    )
                  }
                  iconPosition="right"
                >
                  {postMode === "now"
                    ? "Confirm & Post"
                    : "Confirm & Schedule"}
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </DashboardLayout>
  );
}
