import { useState, useEffect, useCallback, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Building2,
  Globe,
  Users,
  FileText,
  Target,
  Eye,
  MousePointer,
  Heart,
  ShoppingCart,
  Check,
  Brain,
  ChevronDown,
  ChevronUp,
  Megaphone,
  Calendar,
  Rocket,
  Zap,
  BarChart3,
} from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

const TOTAL_STEPS = 7;

const INDUSTRIES = [
  { value: "technology", label: "Technology" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "healthcare", label: "Healthcare" },
  { value: "education", label: "Education" },
  { value: "finance", label: "Finance" },
  { value: "real_estate", label: "Real Estate" },
  { value: "food_beverage", label: "Food & Beverage" },
  { value: "beauty_wellness", label: "Beauty & Wellness" },
  { value: "fitness", label: "Fitness" },
  { value: "travel", label: "Travel" },
  { value: "professional_services", label: "Professional Services" },
  { value: "other", label: "Other" },
];

interface PlatformDef {
  id: string;
  name: string;
  color: string;
  icon: ReactNode;
}

const PLATFORMS: PlatformDef[] = [
  { id: "facebook", name: "Facebook", color: "#1877F2", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> },
  { id: "instagram", name: "Instagram", color: "#E4405F", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678a6.162 6.162 0 100 12.324 6.162 6.162 0 100-12.324zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm7.846-10.405a1.441 1.441 0 11-2.882 0 1.441 1.441 0 012.882 0z"/></svg> },
  { id: "linkedin", name: "LinkedIn", color: "#0A66C2", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg> },
  { id: "twitter", name: "Twitter / X", color: "#1DA1F2", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> },
  { id: "youtube", name: "YouTube", color: "#FF0000", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg> },
  { id: "tiktok", name: "TikTok", color: "#000000", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg> },
  { id: "pinterest", name: "Pinterest", color: "#BD081C", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.781c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12.017 24c6.624 0 11.99-5.367 11.99-11.988C24.007 5.367 18.641 0 12.017 0z"/></svg> },
  { id: "google_business", name: "Google Business", color: "#4285F4", icon: <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" /><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" /><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg> },
];

interface GoalDef {
  id: string;
  label: string;
  icon: ReactNode;
  description: string;
}

const GOALS: GoalDef[] = [
  { id: "brand_awareness", label: "Increase Brand Awareness", icon: <Eye className="w-6 h-6" />, description: "Get your brand in front of more people" },
  { id: "website_traffic", label: "Drive Website Traffic", icon: <MousePointer className="w-6 h-6" />, description: "Bring more visitors to your site" },
  { id: "lead_generation", label: "Generate Leads", icon: <Target className="w-6 h-6" />, description: "Capture and nurture potential customers" },
  { id: "engagement", label: "Boost Engagement", icon: <Heart className="w-6 h-6" />, description: "Increase likes, comments, and shares" },
  { id: "sales", label: "Increase Sales", icon: <ShoppingCart className="w-6 h-6" />, description: "Drive more revenue from social" },
  { id: "community", label: "Build Community", icon: <Users className="w-6 h-6" />, description: "Foster a loyal brand community" },
];

const TONES = [
  "Professional",
  "Casual",
  "Friendly",
  "Authoritative",
  "Playful",
  "Inspirational",
];

const TONE_EXAMPLES: Record<string, string> = {
  Professional: "We're thrilled to announce our latest innovation in marketing automation. Discover how our AI-driven platform can elevate your brand strategy.",
  Casual: "Hey there! Just dropped something awesome - our new AI tool that makes marketing a total breeze. You're gonna love it!",
  Friendly: "Hi friends! We've been working hard on something special for you. Our new AI marketing tool is here to help you shine brighter than ever!",
  Authoritative: "The future of marketing automation is here. Our industry-leading AI platform delivers measurable results with proven strategies.",
  Playful: "Plot twist: marketing just got FUN! Our AI is basically a creative genius in a box. Ready to make some magic happen?",
  Inspirational: "Every great brand starts with a vision. Let our AI help you turn that vision into reality and inspire your audience every single day.",
};

/* -------------------------------------------------------------------------- */
/*  Slide transition variants                                                  */
/* -------------------------------------------------------------------------- */

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -300 : 300,
    opacity: 0,
  }),
};

/* -------------------------------------------------------------------------- */
/*  Main OnboardingPage                                                        */
/* -------------------------------------------------------------------------- */

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [direction, setDirection] = useState(1);

  // Step 2 - Business profile
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [targetAudience, setTargetAudience] = useState("");

  // Step 3 - Platforms
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([]);

  // Step 4 - Goals
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);

  // Step 5 - Brand voice
  const [selectedTones, setSelectedTones] = useState<string[]>([]);
  const [brandDescription, setBrandDescription] = useState("");

  // Step 6 - AI strategy
  const [strategyLoading, setStrategyLoading] = useState(true);
  const [showReasoning, setShowReasoning] = useState(false);

  // Step 7 - Confetti
  const [showConfetti, setShowConfetti] = useState(false);

  function goNext() {
    setDirection(1);
    setStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function goBack() {
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 1));
  }

  function togglePlatform(id: string) {
    setConnectedPlatforms((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  }

  function toggleGoal(id: string) {
    setSelectedGoals((prev) =>
      prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]
    );
  }

  function toggleTone(tone: string) {
    setSelectedTones((prev) =>
      prev.includes(tone) ? prev.filter((t) => t !== tone) : [...prev, tone]
    );
  }

  // Simulate AI strategy load when entering step 6
  useEffect(() => {
    if (step === 6) {
      setStrategyLoading(true);
      const t = setTimeout(() => setStrategyLoading(false), 2500);
      return () => clearTimeout(t);
    }
  }, [step]);

  // Trigger confetti on step 7
  useEffect(() => {
    if (step === 7) {
      setShowConfetti(true);
      const t = setTimeout(() => setShowConfetti(false), 4000);
      return () => clearTimeout(t);
    }
  }, [step]);

  // Save onboarding data
  const saveOnboarding = useCallback(async () => {
    try {
      await api.post("/onboarding/complete", {
        business_name: businessName,
        industry,
        business_description: businessDescription,
        website_url: websiteUrl,
        target_audience: targetAudience,
        connected_platforms: connectedPlatforms,
        goals: selectedGoals,
        brand_tones: selectedTones,
        brand_description: brandDescription,
      });
    } catch {
      // Silent fail - user can complete onboarding later
    }
  }, [businessName, industry, businessDescription, websiteUrl, targetAudience, connectedPlatforms, selectedGoals, selectedTones, brandDescription]);

  useEffect(() => {
    if (step === 7) {
      saveOnboarding();
    }
  }, [step, saveOnboarding]);

  const progress = (step / TOTAL_STEPS) * 100;

  return (
    <div className="relative min-h-screen bg-slate-950 overflow-hidden">
      {/* Background gradients */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full bg-purple-600/10 blur-[120px]" />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full bg-blue-600/10 blur-[120px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-violet-600/5 blur-[100px]" />
      </div>

      {/* Confetti */}
      {showConfetti && <Confetti />}

      {/* Top progress bar */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <div className="h-1 w-full bg-white/5">
          <motion.div
            className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeInOut" }}
          />
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-3 py-6">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map((s) => (
            <div key={s} className="flex items-center gap-3">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300",
                  s < step
                    ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white"
                    : s === step
                      ? "bg-purple-500/20 border-2 border-purple-500 text-purple-400"
                      : "bg-white/5 border border-white/10 text-slate-500"
                )}
              >
                {s < step ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  s
                )}
              </div>
              {s < TOTAL_STEPS && (
                <div
                  className={cn(
                    "w-8 h-0.5 rounded-full transition-colors duration-300",
                    s < step ? "bg-gradient-to-r from-purple-600 to-blue-600" : "bg-white/10"
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen px-4 pt-28 pb-8">
        <div className="w-full max-w-2xl">
          <AnimatePresence mode="wait" custom={direction}>
            {step === 1 && <StepWelcome key="s1" direction={direction} onNext={goNext} />}
            {step === 2 && (
              <StepBusinessProfile
                key="s2"
                direction={direction}
                onNext={goNext}
                onBack={goBack}
                businessName={businessName}
                setBusinessName={setBusinessName}
                industry={industry}
                setIndustry={setIndustry}
                businessDescription={businessDescription}
                setBusinessDescription={setBusinessDescription}
                websiteUrl={websiteUrl}
                setWebsiteUrl={setWebsiteUrl}
                targetAudience={targetAudience}
                setTargetAudience={setTargetAudience}
              />
            )}
            {step === 3 && (
              <StepPlatforms
                key="s3"
                direction={direction}
                onNext={goNext}
                onBack={goBack}
                connectedPlatforms={connectedPlatforms}
                togglePlatform={togglePlatform}
              />
            )}
            {step === 4 && (
              <StepGoals
                key="s4"
                direction={direction}
                onNext={goNext}
                onBack={goBack}
                selectedGoals={selectedGoals}
                toggleGoal={toggleGoal}
              />
            )}
            {step === 5 && (
              <StepBrandVoice
                key="s5"
                direction={direction}
                onNext={goNext}
                onBack={goBack}
                selectedTones={selectedTones}
                toggleTone={toggleTone}
                brandDescription={brandDescription}
                setBrandDescription={setBrandDescription}
              />
            )}
            {step === 6 && (
              <StepStrategy
                key="s6"
                direction={direction}
                onNext={goNext}
                onBack={goBack}
                loading={strategyLoading}
                connectedPlatforms={connectedPlatforms}
                showReasoning={showReasoning}
                setShowReasoning={setShowReasoning}
              />
            )}
            {step === 7 && (
              <StepCompletion
                key="s7"
                direction={direction}
                connectedPlatforms={connectedPlatforms}
                selectedGoals={selectedGoals}
                navigate={navigate}
              />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 1 - Welcome                                                           */
/* -------------------------------------------------------------------------- */

function StepWelcome({ direction, onNext }: { direction: number; onNext: () => void }) {
  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
      className="text-center space-y-8"
    >
      {/* Animated illustration */}
      <div className="flex justify-center">
        <div className="relative">
          <motion.div
            animate={{
              scale: [1, 1.05, 1],
              rotate: [0, 3, -3, 0],
            }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            className="w-40 h-40 rounded-full bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center"
          >
            <div className="w-28 h-28 rounded-full bg-gradient-to-br from-purple-600/40 to-blue-600/40 flex items-center justify-center">
              <Megaphone className="w-12 h-12 text-purple-300" />
            </div>
          </motion.div>

          {/* Floating sparkles */}
          {[
            { top: "-8px", right: "0px", delay: 0 },
            { top: "20px", right: "-20px", delay: 0.5 },
            { bottom: "10px", left: "-16px", delay: 1 },
            { top: "4px", left: "0px", delay: 1.5 },
          ].map((pos, i) => (
            <motion.div
              key={i}
              animate={{
                y: [0, -8, 0],
                opacity: [0.4, 1, 0.4],
              }}
              transition={{ duration: 2, repeat: Infinity, delay: pos.delay }}
              className="absolute"
              style={pos}
            >
              <Sparkles className="w-5 h-5 text-purple-400" />
            </motion.div>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <h1 className="text-4xl font-bold">
          <span className="bg-gradient-to-r from-purple-400 via-violet-400 to-blue-400 bg-clip-text text-transparent">
            Welcome to MarketEngine!
          </span>
        </h1>
        <p className="text-lg text-slate-400 max-w-md mx-auto">
          Let's set up your AI marketing engine in under 5 minutes
        </p>
      </div>

      <div className="flex justify-center pt-4">
        <Button size="xl" onClick={onNext} icon={<Rocket className="w-5 h-5" />} iconPosition="right">
          Let's Get Started
        </Button>
      </div>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 2 - Business Profile                                                  */
/* -------------------------------------------------------------------------- */

interface StepBusinessProfileProps {
  direction: number;
  onNext: () => void;
  onBack: () => void;
  businessName: string;
  setBusinessName: (v: string) => void;
  industry: string;
  setIndustry: (v: string) => void;
  businessDescription: string;
  setBusinessDescription: (v: string) => void;
  websiteUrl: string;
  setWebsiteUrl: (v: string) => void;
  targetAudience: string;
  setTargetAudience: (v: string) => void;
}

function StepBusinessProfile({
  direction,
  onNext,
  onBack,
  businessName,
  setBusinessName,
  industry,
  setIndustry,
  businessDescription,
  setBusinessDescription,
  websiteUrl,
  setWebsiteUrl,
  targetAudience,
  setTargetAudience,
}: StepBusinessProfileProps) {
  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
    >
      <GlassCard className="!bg-white/[0.03] border-white/[0.06]" padding="lg">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-purple-500/15 border border-purple-500/20 mb-2">
              <Building2 className="w-6 h-6 text-purple-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">Tell Us About Your Business</h2>
            <p className="text-sm text-slate-400">This helps our AI create the perfect strategy</p>
          </div>

          <div className="space-y-4">
            <Input
              label="Business name"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              icon={<Building2 className="w-4 h-4" />}
              placeholder="Acme Inc."
            />

            <Select
              label="Industry"
              options={INDUSTRIES}
              value={industry}
              onChange={setIndustry}
              placeholder="Select your industry"
            />

            <div className="relative">
              <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
                Business description
              </label>
              <textarea
                value={businessDescription}
                onChange={(e) => setBusinessDescription(e.target.value)}
                placeholder="Briefly describe what your business does..."
                rows={3}
                className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 placeholder-gray-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
              />
            </div>

            <Input
              label="Website URL"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              icon={<Globe className="w-4 h-4" />}
              placeholder="https://yoursite.com"
            />

            <div className="relative">
              <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
                Target audience
              </label>
              <textarea
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="Describe your ideal customer (e.g. age, interests, profession)..."
                rows={2}
                className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 placeholder-gray-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
              />
            </div>
          </div>

          <NavigationButtons onBack={onBack} onNext={onNext} nextDisabled={!businessName.trim()} />
        </div>
      </GlassCard>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 3 - Connect Platforms                                                 */
/* -------------------------------------------------------------------------- */

interface StepPlatformsProps {
  direction: number;
  onNext: () => void;
  onBack: () => void;
  connectedPlatforms: string[];
  togglePlatform: (id: string) => void;
}

function StepPlatforms({ direction, onNext, onBack, connectedPlatforms, togglePlatform }: StepPlatformsProps) {
  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
    >
      <GlassCard className="!bg-white/[0.03] border-white/[0.06]" padding="lg">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-500/15 border border-blue-500/20 mb-2">
              <Globe className="w-6 h-6 text-blue-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">Connect Your Social Media</h2>
            <p className="text-sm text-slate-400">
              Connect at least 1 platform to get started
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {PLATFORMS.map((platform) => {
              const isConnected = connectedPlatforms.includes(platform.id);
              return (
                <motion.button
                  key={platform.id}
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => togglePlatform(platform.id)}
                  className={cn(
                    "relative flex flex-col items-center gap-2.5 p-4 rounded-xl border transition-all duration-200",
                    isConnected
                      ? "bg-emerald-500/10 border-emerald-500/30"
                      : "bg-white/5 border-white/10 hover:bg-white/[0.08] hover:border-white/20"
                  )}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ backgroundColor: `${platform.color}20`, color: platform.color }}
                  >
                    {platform.icon}
                  </div>
                  <span className="text-sm font-medium text-white">{platform.name}</span>

                  {isConnected ? (
                    <Badge variant="success" size="sm">
                      <Check className="w-3 h-3" /> Connected
                    </Badge>
                  ) : (
                    <span className="text-xs text-slate-500">Click to connect</span>
                  )}

                  {isConnected && (
                    <div className="absolute top-2 right-2">
                      <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    </div>
                  )}
                </motion.button>
              );
            })}
          </div>

          <NavigationButtons onBack={onBack} onNext={onNext}>
            <button
              type="button"
              onClick={onNext}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors underline underline-offset-2"
            >
              Skip for now
            </button>
          </NavigationButtons>
        </div>
      </GlassCard>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 4 - Goals                                                             */
/* -------------------------------------------------------------------------- */

interface StepGoalsProps {
  direction: number;
  onNext: () => void;
  onBack: () => void;
  selectedGoals: string[];
  toggleGoal: (id: string) => void;
}

function StepGoals({ direction, onNext, onBack, selectedGoals, toggleGoal }: StepGoalsProps) {
  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
    >
      <GlassCard className="!bg-white/[0.03] border-white/[0.06]" padding="lg">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-violet-500/15 border border-violet-500/20 mb-2">
              <Target className="w-6 h-6 text-violet-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">What Are Your Marketing Goals?</h2>
            <p className="text-sm text-slate-400">Select all that apply</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {GOALS.map((goal) => {
              const isSelected = selectedGoals.includes(goal.id);
              return (
                <motion.button
                  key={goal.id}
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => toggleGoal(goal.id)}
                  className={cn(
                    "relative flex flex-col items-center gap-3 p-5 rounded-xl border transition-all duration-200 text-center",
                    isSelected
                      ? "bg-purple-500/10 border-purple-500/40 shadow-lg shadow-purple-500/10"
                      : "bg-white/5 border-white/10 hover:bg-white/[0.08] hover:border-white/20"
                  )}
                >
                  <div
                    className={cn(
                      "w-12 h-12 rounded-xl flex items-center justify-center transition-colors",
                      isSelected
                        ? "bg-purple-500/20 text-purple-400"
                        : "bg-white/10 text-slate-400"
                    )}
                  >
                    {goal.icon}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{goal.label}</p>
                    <p className="text-[11px] text-slate-500 mt-1">{goal.description}</p>
                  </div>

                  {isSelected && (
                    <div className="absolute top-2.5 right-2.5">
                      <div className="w-5 h-5 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    </div>
                  )}
                </motion.button>
              );
            })}
          </div>

          <NavigationButtons onBack={onBack} onNext={onNext} nextDisabled={selectedGoals.length === 0} />
        </div>
      </GlassCard>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 5 - Brand Voice                                                       */
/* -------------------------------------------------------------------------- */

interface StepBrandVoiceProps {
  direction: number;
  onNext: () => void;
  onBack: () => void;
  selectedTones: string[];
  toggleTone: (tone: string) => void;
  brandDescription: string;
  setBrandDescription: (v: string) => void;
}

function StepBrandVoice({
  direction,
  onNext,
  onBack,
  selectedTones,
  toggleTone,
  brandDescription,
  setBrandDescription,
}: StepBrandVoiceProps) {
  const previewTone = selectedTones.length > 0 ? selectedTones[selectedTones.length - 1] : null;

  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
    >
      <GlassCard className="!bg-white/[0.03] border-white/[0.06]" padding="lg">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-pink-500/15 border border-pink-500/20 mb-2">
              <FileText className="w-6 h-6 text-pink-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">Define Your Brand Voice</h2>
            <p className="text-sm text-slate-400">How should your content sound?</p>
          </div>

          {/* Tone pills */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-3 pl-1">
              Select your brand tones
            </label>
            <div className="flex flex-wrap gap-2">
              {TONES.map((tone) => {
                const isSelected = selectedTones.includes(tone);
                return (
                  <motion.button
                    key={tone}
                    type="button"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => toggleTone(tone)}
                    className={cn(
                      "px-4 py-2 rounded-full text-sm font-medium border transition-all duration-200",
                      isSelected
                        ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 border-purple-500/40 text-purple-300"
                        : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10 hover:text-white"
                    )}
                  >
                    {isSelected && <Check className="w-3.5 h-3.5 inline mr-1.5" />}
                    {tone}
                  </motion.button>
                );
              })}
            </div>
          </div>

          {/* Brand description */}
          <div className="relative">
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
              Brand description
            </label>
            <textarea
              value={brandDescription}
              onChange={(e) => setBrandDescription(e.target.value)}
              placeholder="Describe your brand's personality and values..."
              rows={3}
              className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 placeholder-gray-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
            />
          </div>

          {/* Example preview */}
          {previewTone && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4 space-y-2"
            >
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-medium text-amber-400">
                  Example post - {previewTone} tone
                </span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed italic">
                "{TONE_EXAMPLES[previewTone]}"
              </p>
            </motion.div>
          )}

          <NavigationButtons onBack={onBack} onNext={onNext} nextDisabled={selectedTones.length === 0} />
        </div>
      </GlassCard>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 6 - AI Strategy                                                       */
/* -------------------------------------------------------------------------- */

interface StepStrategyProps {
  direction: number;
  onNext: () => void;
  onBack: () => void;
  loading: boolean;
  connectedPlatforms: string[];
  showReasoning: boolean;
  setShowReasoning: (v: boolean) => void;
}

function StepStrategy({
  direction,
  onNext,
  onBack,
  loading,
  connectedPlatforms,
  showReasoning,
  setShowReasoning,
}: StepStrategyProps) {
  // Generate mock data based on connected platforms
  const platformMix = connectedPlatforms.length > 0
    ? connectedPlatforms.map((id, i) => {
        const platform = PLATFORMS.find((p) => p.id === id);
        const percentages = [35, 25, 20, 10, 5, 3, 1, 1];
        return {
          name: platform?.name ?? id,
          color: platform?.color ?? "#6B7280",
          percentage: percentages[i] ?? 5,
        };
      })
    : [
        { name: "Instagram", color: "#E4405F", percentage: 35 },
        { name: "LinkedIn", color: "#0A66C2", percentage: 30 },
        { name: "Twitter / X", color: "#1DA1F2", percentage: 20 },
        { name: "Facebook", color: "#1877F2", percentage: 15 },
      ];

  // Normalize to 100%
  const total = platformMix.reduce((sum, p) => sum + p.percentage, 0);
  const normalized = platformMix.map((p) => ({
    ...p,
    percentage: Math.round((p.percentage / total) * 100),
  }));

  const themes = [
    { title: "Educational Content", description: "Tips, tutorials, and how-to guides", icon: <FileText className="w-5 h-5" /> },
    { title: "Behind the Scenes", description: "Team culture and company stories", icon: <Users className="w-5 h-5" /> },
    { title: "Product Showcases", description: "Features, updates, and use cases", icon: <Sparkles className="w-5 h-5" /> },
  ];

  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
    >
      <GlassCard className="!bg-white/[0.03] border-white/[0.06]" padding="lg">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-cyan-500/15 border border-cyan-500/20 mb-2">
              <Brain className="w-6 h-6 text-cyan-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">Your AI Marketing Strategy</h2>
            <p className="text-sm text-slate-400">Powered by advanced AI analysis</p>
          </div>

          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center py-12 space-y-4"
              >
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                >
                  <Brain className="w-12 h-12 text-purple-400" />
                </motion.div>
                <div className="text-center">
                  <p className="text-white font-medium">Analyzing your business...</p>
                  <p className="text-sm text-slate-500 mt-1">This will only take a moment</p>
                </div>
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.3 }}
                      className="w-2 h-2 rounded-full bg-purple-500"
                    />
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="results"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-5"
              >
                {/* Platform mix */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-purple-400" />
                    Platform Allocation
                  </h3>
                  <div className="space-y-2.5">
                    {normalized.map((p) => (
                      <div key={p.name} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400">{p.name}</span>
                          <span className="text-white font-medium">{p.percentage}%</span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${p.percentage}%` }}
                            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
                            className="h-full rounded-full"
                            style={{ backgroundColor: p.color }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Posting frequency */}
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4">
                  <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-blue-400" />
                    Recommended Posting Frequency
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {normalized.slice(0, 4).map((p) => (
                      <div key={p.name} className="flex items-center justify-between text-xs bg-white/5 rounded-lg px-3 py-2">
                        <span className="text-slate-400">{p.name}</span>
                        <span className="text-white font-medium">
                          {p.percentage > 25 ? "5x/week" : p.percentage > 15 ? "3x/week" : "2x/week"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Content themes */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-slate-300">Top Content Themes</h3>
                  <div className="grid grid-cols-3 gap-2">
                    {themes.map((theme) => (
                      <div
                        key={theme.title}
                        className="flex flex-col items-center text-center gap-2 p-3 rounded-xl bg-white/5 border border-white/[0.06]"
                      >
                        <div className="w-9 h-9 rounded-lg bg-purple-500/15 flex items-center justify-center text-purple-400">
                          {theme.icon}
                        </div>
                        <p className="text-xs font-medium text-white leading-tight">{theme.title}</p>
                        <p className="text-[10px] text-slate-500 leading-tight">{theme.description}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI confidence */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-emerald-300 font-medium">AI Confidence Score</span>
                  </div>
                  <span className="text-lg font-bold text-emerald-400">94%</span>
                </div>

                {/* AI reasoning */}
                <div>
                  <button
                    type="button"
                    onClick={() => setShowReasoning(!showReasoning)}
                    className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    {showReasoning ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    AI Reasoning
                  </button>
                  <AnimatePresence>
                    {showReasoning && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.3 }}
                        className="overflow-hidden"
                      >
                        <p className="mt-3 text-xs text-slate-500 leading-relaxed bg-white/[0.02] border border-white/5 rounded-xl p-4">
                          Based on your industry profile and target audience, I recommend a
                          content-heavy approach focused on visual platforms. Your audience
                          engagement patterns suggest peak activity during weekday mornings and
                          evenings. The strategy prioritizes platforms where your target
                          demographic is most active, with a mix of educational, promotional,
                          and community-building content to maximize reach and conversions.
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {!loading && <NavigationButtons onBack={onBack} onNext={onNext} nextLabel="Continue" />}
        </div>
      </GlassCard>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Step 7 - Completion                                                        */
/* -------------------------------------------------------------------------- */

interface StepCompletionProps {
  direction: number;
  connectedPlatforms: string[];
  selectedGoals: string[];
  navigate: ReturnType<typeof useNavigate>;
}

function StepCompletion({ direction, connectedPlatforms, selectedGoals, navigate }: StepCompletionProps) {
  return (
    <motion.div
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ duration: 0.4, ease: "easeInOut" }}
      className="text-center space-y-8"
    >
      {/* Celebration icon */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 12, delay: 0.2 }}
        className="flex justify-center"
      >
        <div className="relative">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center">
            <Check className="w-12 h-12 text-purple-400" />
          </div>
          {/* Pulse rings */}
          <motion.div
            animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="absolute inset-0 rounded-full border-2 border-purple-500/30"
          />
          <motion.div
            animate={{ scale: [1, 1.8], opacity: [0.3, 0] }}
            transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
            className="absolute inset-0 rounded-full border-2 border-blue-500/20"
          />
        </div>
      </motion.div>

      <div className="space-y-3">
        <h1 className="text-4xl font-bold">
          <span className="bg-gradient-to-r from-purple-400 via-violet-400 to-blue-400 bg-clip-text text-transparent">
            You're All Set!
          </span>
        </h1>
        <p className="text-slate-400 max-w-sm mx-auto">
          Your AI marketing engine is configured and ready to create amazing content.
        </p>
      </div>

      {/* Summary card */}
      <GlassCard className="!bg-white/[0.03] border-white/[0.06] text-left" padding="md">
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white">Setup Summary</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-3 rounded-xl bg-white/5">
              <p className="text-2xl font-bold text-purple-400">{connectedPlatforms.length}</p>
              <p className="text-[11px] text-slate-500 mt-1">Platforms Connected</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-white/5">
              <p className="text-2xl font-bold text-blue-400">{selectedGoals.length}</p>
              <p className="text-[11px] text-slate-500 mt-1">Goals Set</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-white/5">
              <p className="text-2xl font-bold text-emerald-400">1</p>
              <p className="text-[11px] text-slate-500 mt-1">Strategy Generated</p>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Action buttons */}
      <div className="space-y-3 pt-2">
        <Button
          size="xl"
          fullWidth
          onClick={() => navigate("/dashboard")}
          icon={<ArrowRight className="w-5 h-5" />}
          iconPosition="right"
        >
          Go to Dashboard
        </Button>
        <Button
          size="lg"
          variant="secondary"
          fullWidth
          onClick={() => navigate("/calendar")}
          icon={<Calendar className="w-4 h-4" />}
        >
          View Content Calendar
        </Button>
      </div>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Shared Navigation Buttons                                                  */
/* -------------------------------------------------------------------------- */

interface NavigationButtonsProps {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  children?: ReactNode;
}

function NavigationButtons({ onBack, onNext, nextLabel = "Next", nextDisabled, children }: NavigationButtonsProps) {
  return (
    <div className="flex items-center justify-between pt-2">
      <div className="flex items-center gap-4">
        {onBack && (
          <Button variant="ghost" onClick={onBack} icon={<ArrowLeft className="w-4 h-4" />}>
            Back
          </Button>
        )}
        {children}
      </div>
      <Button
        onClick={onNext}
        disabled={nextDisabled}
        icon={<ArrowRight className="w-4 h-4" />}
        iconPosition="right"
      >
        {nextLabel}
      </Button>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Confetti Component                                                         */
/* -------------------------------------------------------------------------- */

function Confetti() {
  const colors = ["#8B5CF6", "#6366F1", "#3B82F6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#EC4899"];

  return (
    <div className="fixed inset-0 pointer-events-none z-[100] overflow-hidden">
      {Array.from({ length: 60 }).map((_, i) => {
        const left = Math.random() * 100;
        const delay = Math.random() * 2;
        const duration = 2.5 + Math.random() * 2;
        const color = colors[i % colors.length];
        const size = 6 + Math.random() * 8;
        const rotation = Math.random() * 360;

        return (
          <motion.div
            key={i}
            initial={{
              x: `${left}vw`,
              y: -20,
              rotate: rotation,
              opacity: 1,
            }}
            animate={{
              y: "110vh",
              rotate: rotation + 360 + Math.random() * 360,
              x: `${left + (Math.random() - 0.5) * 30}vw`,
              opacity: [1, 1, 0],
            }}
            transition={{
              duration,
              delay,
              ease: "easeIn",
            }}
            style={{
              position: "absolute",
              width: size,
              height: size * (Math.random() > 0.5 ? 1 : 0.6),
              backgroundColor: color,
              borderRadius: Math.random() > 0.5 ? "50%" : "2px",
            }}
          />
        );
      })}
    </div>
  );
}
