import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence, MotionConfig } from "framer-motion";
import { EASE } from "@/components/shared/motion";
import {
  Check,
  X,
  ChevronDown,
  Zap,
  ArrowRight,
  Building2,
  MessageSquare,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

interface PlanFeature {
  text: string;
  included: boolean;
}

interface Plan {
  name: string;
  monthlyPrice: number;
  description: string;
  features: PlanFeature[];
  popular?: boolean;
  cta: string;
}

const plans: Plan[] = [
  {
    name: "Starter",
    monthlyPrice: 49,
    description: "Perfect for solopreneurs and small businesses getting started.",
    cta: "Start Free Trial",
    features: [
      { text: "1 brand", included: true },
      { text: "3 social platforms", included: true },
      { text: "30 posts per month", included: true },
      { text: "Basic analytics", included: true },
      { text: "AI content generation", included: true },
      { text: "Email support", included: true },
      { text: "A/B testing", included: false },
      { text: "AI strategy engine", included: false },
      { text: "Team members", included: false },
      { text: "Paid ads management", included: false },
    ],
  },
  {
    name: "Growth",
    monthlyPrice: 149,
    description: "For growing businesses ready to scale their social presence.",
    popular: true,
    cta: "Start Free Trial",
    features: [
      { text: "1 brand", included: true },
      { text: "6 social platforms", included: true },
      { text: "100 posts per month", included: true },
      { text: "Advanced analytics", included: true },
      { text: "AI content generation", included: true },
      { text: "Priority support", included: true },
      { text: "A/B testing", included: true },
      { text: "AI strategy engine", included: true },
      { text: "Team members", included: false },
      { text: "Paid ads management", included: false },
    ],
  },
  {
    name: "Pro",
    monthlyPrice: 399,
    description: "For agencies and teams managing multiple brands at scale.",
    cta: "Start Free Trial",
    features: [
      { text: "3 brands", included: true },
      { text: "All social platforms", included: true },
      { text: "Unlimited content", included: true },
      { text: "Advanced analytics", included: true },
      { text: "AI content generation", included: true },
      { text: "Dedicated account manager", included: true },
      { text: "A/B testing", included: true },
      { text: "AI strategy engine", included: true },
      { text: "5 team members", included: true },
      { text: "Paid ads management", included: true },
      { text: "Competitor intelligence", included: true },
      { text: "White-label option", included: true },
    ],
  },
];

const faqs = [
  {
    question: "What is MarketEngine?",
    answer:
      "MarketEngine is an AI-powered marketing automation platform that helps businesses plan, create, schedule, and optimize social media content across all major platforms. Our AI engine analyzes your business, audience, and industry to deliver data-driven strategies and ready-to-publish content.",
  },
  {
    question: "How does the AI content generation work?",
    answer:
      "Our AI analyzes your brand voice, target audience, industry trends, and top-performing content to generate platform-optimized posts. You can generate captions, hashtags, image suggestions, and even full campaign strategies. Every piece of content is customizable before publishing.",
  },
  {
    question: "Which social media platforms are supported?",
    answer:
      "We currently support Facebook, Instagram, LinkedIn, Twitter/X, YouTube, TikTok, and Pinterest. We are actively adding more platforms, and Enterprise customers can request custom integrations for any platform.",
  },
  {
    question: "Can I cancel anytime?",
    answer:
      "Absolutely. There are no long-term contracts or cancellation fees. You can cancel your subscription at any time from your account settings, and you will retain access to your plan until the end of your current billing cycle.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes! Every plan comes with a 14-day free trial. No credit card is required to start. You get full access to all features in your chosen plan during the trial period.",
  },
  {
    question: "How does team collaboration work?",
    answer:
      "On the Pro plan and above, you can invite team members with role-based access controls. Roles include Admin, Editor, and Viewer. You can set up approval workflows so content is reviewed before publishing, and team members can leave comments directly on content drafts.",
  },
  {
    question: "What payment methods do you accept?",
    answer:
      "We accept all major credit and debit cards (Visa, Mastercard, American Express, Discover), as well as PayPal. Enterprise customers can also pay via invoice with NET 30 terms.",
  },
  {
    question: "Do you offer refunds?",
    answer:
      "We offer a full refund within the first 30 days of any paid subscription if you are not satisfied. After 30 days, you can cancel at any time but refunds are not provided for partial billing periods. Our 14-day free trial lets you test everything before committing.",
  },
];

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function PricingToggle({
  annual,
  onChange,
}: {
  annual: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="mb-16 flex items-center justify-center gap-4">
      <span
        className={cn(
          "text-sm font-medium transition-colors",
          !annual ? "text-white" : "text-slate-500"
        )}
      >
        Monthly
      </span>
      <button
        onClick={() => onChange(!annual)}
        className={cn(
          "relative h-7 w-14 rounded-full border transition-colors",
          annual
            ? "border-purple-500/40 bg-purple-600/30"
            : "border-white/10 bg-white/10"
        )}
      >
        <motion.div
          layout
          className="absolute top-0.5 h-6 w-6 rounded-full bg-white shadow-md"
          style={{ left: annual ? "calc(100% - 26px)" : "2px" }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </button>
      <span
        className={cn(
          "text-sm font-medium transition-colors",
          annual ? "text-white" : "text-slate-500"
        )}
      >
        Annual
      </span>
      {annual && (
        <Badge variant="success" className="ml-1">
          Save 20%
        </Badge>
      )}
    </div>
  );
}

function PricingCard({
  plan,
  annual,
}: {
  plan: Plan;
  annual: boolean;
}) {
  const navigate = useNavigate();
  const price = annual
    ? Math.round(plan.monthlyPrice * 0.8)
    : plan.monthlyPrice;

  return (
    <div className="relative h-full">
      {plan.popular && (
        <div className="absolute -top-3 left-1/2 z-20 -translate-x-1/2">
          <Badge
            variant="info"
            className="bg-gradient-to-r from-purple-600 to-blue-600 border-0 px-4 py-1 text-white shadow-lg shadow-purple-500/25"
          >
            Most Popular
          </Badge>
        </div>
      )}

      <GlassCard
        hover
        glow={plan.popular}
        padding="lg"
        className={cn(
          "flex h-full flex-col",
          plan.popular && "border-purple-500/30 shadow-lg shadow-purple-500/10"
        )}
      >
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
          <p className="mt-1 text-sm text-slate-400">{plan.description}</p>
        </div>

        <div className="mb-6">
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-bold text-white">${price}</span>
            <span className="text-sm text-slate-500">/month</span>
          </div>
          {annual && (
            <p className="mt-1 text-xs text-slate-500">
              Billed ${price * 12}/year
            </p>
          )}
        </div>

        <Button
          variant={plan.popular ? "primary" : "secondary"}
          size={plan.popular ? "lg" : "md"}
          fullWidth
          icon={<ArrowRight className="h-4 w-4" />}
          iconPosition="right"
          onClick={() => navigate("/register")}
        >
          {plan.cta}
        </Button>

        <div className="mt-8 flex-1">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            What's included
          </p>
          <ul className="space-y-3">
            {plan.features.map((f) => (
              <li key={f.text} className="flex items-start gap-2.5">
                {f.included ? (
                  <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-400" />
                ) : (
                  <X className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-600" />
                )}
                <span
                  className={cn(
                    "text-sm",
                    f.included ? "text-slate-300" : "text-slate-600"
                  )}
                >
                  {f.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </GlassCard>
    </div>
  );
}

function FaqItem({
  question,
  answer,
  isOpen,
  onToggle,
}: {
  question: string;
  answer: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-6 py-5 text-left transition-colors hover:bg-white/5"
      >
        <span className="pr-4 text-sm font-medium text-white sm:text-base">
          {question}
        </span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-5 w-5 flex-shrink-0 text-slate-400" />
        </motion.div>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="border-t border-white/5 px-6 py-5">
              <p className="text-sm leading-relaxed text-slate-400">{answer}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Pricing page                                                       */
/* ------------------------------------------------------------------ */

export default function PricingPage() {
  const navigate = useNavigate();
  const [annual, setAnnual] = useState(true);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <PublicLayout>
      {/* Hero / Header */}
      <section className="relative overflow-hidden pt-32 pb-20">
        {/* Gradient mesh */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-1/4 left-1/3 h-[500px] w-[500px] rounded-full bg-purple-700/20 blur-[160px]" />
          <div className="absolute -top-1/4 right-1/3 h-[400px] w-[400px] rounded-full bg-blue-700/15 blur-[140px]" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Badge variant="info" className="mb-6 px-4 py-1.5 text-sm">
              <Zap className="mr-1.5 inline h-3.5 w-3.5" />
              14-day free trial on all plans
            </Badge>
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl">
              Simple,{" "}
              <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                Transparent
              </span>{" "}
              Pricing
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
              Choose the plan that's right for your business. All plans include
              a 14-day free trial with full access.
            </p>
          </motion.div>

          {/* Toggle */}
          <div className="mt-12">
            <PricingToggle annual={annual} onChange={setAnnual} />
          </div>

          {/* Pricing cards */}
          <div className="grid items-stretch gap-6 md:grid-cols-3">
            {plans.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 40 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: i * 0.12 }}
                className="h-full"
              >
                <PricingCard plan={plan} annual={annual} />
              </motion.div>
            ))}
          </div>

          {/* Enterprise card */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="mt-8"
          >
            <GlassCard padding="lg">
              <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20">
                    <Building2 className="h-6 w-6 text-purple-400" />
                  </div>
                  <div className="text-left">
                    <h3 className="text-lg font-semibold text-white">
                      Enterprise
                    </h3>
                    <p className="text-sm text-slate-400">
                      Need more? Custom integrations, dedicated manager, SLA
                      guarantees, and unlimited everything.
                    </p>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="lg"
                  icon={<MessageSquare className="h-4 w-4" />}
                  onClick={() => navigate("/contact")}
                  className="flex-shrink-0"
                >
                  Contact Sales
                </Button>
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="relative py-24">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-[400px] w-[400px] -translate-x-1/2 rounded-full bg-purple-700/10 blur-[140px]" />
        </div>

        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Frequently Asked Questions
            </h2>
            <p className="mt-4 text-lg text-slate-400">
              Got questions? We have answers.
            </p>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <motion.div
                key={faq.question}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <FaqItem
                  question={faq.question}
                  answer={faq.answer}
                  isOpen={openFaq === i}
                  onToggle={() =>
                    setOpenFaq(openFaq === i ? null : i)
                  }
                />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="relative py-24">
        <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Still have questions?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-lg text-slate-400">
              Our team is here to help. Reach out and we will get back to you
              within 24 hours.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button
                size="xl"
                variant="primary"
                icon={<ArrowRight className="h-5 w-5" />}
                iconPosition="right"
                onClick={() => navigate("/register")}
              >
                Start Free Trial
              </Button>
              <Button
                size="xl"
                variant="secondary"
                icon={<MessageSquare className="h-4 w-4" />}
                onClick={() => navigate("/contact")}
              >
                Talk to Sales
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </PublicLayout>
  );
}
