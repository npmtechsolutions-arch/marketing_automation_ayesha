import { useState } from "react";
import { motion } from "framer-motion";
import {
  CreditCard,
  Check,
  Download,
  ArrowUpRight,
  Zap,
  Crown,
  Rocket,
  Users,
  Share2,
  FileText,
  Calendar,
  Sparkles,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

// ── Types & Mock Data ───────────────────────────────────────────────

interface PlanFeature {
  text: string;
  included: boolean;
}

interface PricingPlan {
  id: string;
  name: string;
  icon: React.ElementType;
  monthlyPrice: number;
  annualPrice: number;
  description: string;
  popular?: boolean;
  features: PlanFeature[];
  posts: number;
  members: number;
  platforms: number;
}

const plans: PricingPlan[] = [
  {
    id: "starter",
    name: "Starter",
    icon: Zap,
    monthlyPrice: 49,
    annualPrice: 39,
    description: "Perfect for solopreneurs and small teams getting started",
    features: [
      { text: "Up to 100 posts/month", included: true },
      { text: "3 team members", included: true },
      { text: "5 social platforms", included: true },
      { text: "Basic analytics", included: true },
      { text: "AI content suggestions", included: true },
      { text: "Email support", included: true },
      { text: "Advanced AI strategies", included: false },
      { text: "White-label reports", included: false },
      { text: "Priority support", included: false },
    ],
    posts: 100,
    members: 3,
    platforms: 5,
  },
  {
    id: "growth",
    name: "Growth",
    icon: Rocket,
    monthlyPrice: 149,
    annualPrice: 119,
    description: "For growing teams that need more power and flexibility",
    popular: true,
    features: [
      { text: "Up to 500 posts/month", included: true },
      { text: "10 team members", included: true },
      { text: "All social platforms", included: true },
      { text: "Advanced analytics", included: true },
      { text: "AI content generation", included: true },
      { text: "AI strategy recommendations", included: true },
      { text: "Campaign management", included: true },
      { text: "Priority email support", included: true },
      { text: "White-label reports", included: false },
    ],
    posts: 500,
    members: 10,
    platforms: 8,
  },
  {
    id: "pro",
    name: "Pro",
    icon: Crown,
    monthlyPrice: 399,
    annualPrice: 319,
    description: "For agencies and enterprises with advanced needs",
    features: [
      { text: "Unlimited posts", included: true },
      { text: "Unlimited team members", included: true },
      { text: "All social platforms", included: true },
      { text: "Custom analytics dashboards", included: true },
      { text: "Advanced AI content suite", included: true },
      { text: "Custom AI brand voice", included: true },
      { text: "White-label reports", included: true },
      { text: "API access", included: true },
      { text: "Dedicated account manager", included: true },
    ],
    posts: -1,
    members: -1,
    platforms: 8,
  },
];

const currentPlanId = "growth";

const usage = {
  posts: { used: 312, limit: 500 },
  members: { used: 7, limit: 10 },
  platforms: { used: 5, limit: 8 },
};

const mockInvoices = [
  { id: "INV-2026-003", date: "Mar 1, 2026", description: "Growth Plan - Monthly", amount: 149.0, status: "paid" as const },
  { id: "INV-2026-002", date: "Feb 1, 2026", description: "Growth Plan - Monthly", amount: 149.0, status: "paid" as const },
  { id: "INV-2026-001", date: "Jan 1, 2026", description: "Growth Plan - Monthly", amount: 149.0, status: "paid" as const },
  { id: "INV-2025-012", date: "Dec 1, 2025", description: "Growth Plan - Monthly", amount: 149.0, status: "paid" as const },
  { id: "INV-2025-011", date: "Nov 1, 2025", description: "Starter Plan - Monthly + Upgrade", amount: 198.0, status: "paid" as const },
];

// ── Component ───────────────────────────────────────────────────────

function UsageMeter({ label, used, limit, icon }: { label: string; used: number; limit: number; icon: React.ReactNode }) {
  const pct = limit === -1 ? 0 : (used / limit) * 100;
  const isUnlimited = limit === -1;
  const isHigh = pct > 80;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm" style={{ color: "var(--page-text)" }}>{label}</span>
        </div>
        <span className={cn("text-sm font-medium tabular-nums", isHigh && "text-amber-400")} style={!isHigh ? { color: "var(--page-text)" } : undefined}>
          {used}{isUnlimited ? "" : ` / ${limit}`}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--sidebar-hover-bg)" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: isUnlimited ? "5%" : `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={cn("h-full rounded-full", isHigh ? "bg-gradient-to-r from-amber-500 to-orange-500" : "bg-gradient-to-r from-purple-500 to-blue-500")}
        />
      </div>
    </div>
  );
}

export default function BillingPage() {
  const [annual, setAnnual] = useState(false);
  const currentPlan = plans.find((p) => p.id === currentPlanId)!;

  return (
    <DashboardLayout>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="mb-8">
        <h1 className="text-3xl font-bold" style={{ color: "var(--page-heading)" }}>Billing & Subscription</h1>
        <p className="mt-1" style={{ color: "var(--page-text-secondary)" }}>Manage your plan, payment method, and billing history</p>
      </motion.div>

      {/* Current Plan */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }}>
        <GlassCard glow className="mb-8">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center">
                  <currentPlan.icon className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold" style={{ color: "var(--page-heading)" }}>{currentPlan.name} Plan</h2>
                    <Badge variant="info">Current</Badge>
                  </div>
                  <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>{currentPlan.description}</p>
                </div>
              </div>
              <div className="mt-4">
                <span className="text-4xl font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>${annual ? currentPlan.annualPrice : currentPlan.monthlyPrice}</span>
                <span className="text-sm" style={{ color: "var(--page-text-secondary)" }}>/month</span>
              </div>
              <p className="text-xs mt-1" style={{ color: "var(--page-text-muted)" }}>
                <Calendar className="w-3.5 h-3.5 inline mr-1" />
                Next renewal: April 1, 2026
              </p>
            </div>
            <div className="flex-1 space-y-4">
              <UsageMeter label="Posts" used={usage.posts.used} limit={usage.posts.limit} icon={<FileText className="w-4 h-4 text-purple-400" />} />
              <UsageMeter label="Team Members" used={usage.members.used} limit={usage.members.limit} icon={<Users className="w-4 h-4 text-blue-400" />} />
              <UsageMeter label="Platforms" used={usage.platforms.used} limit={usage.platforms.limit} icon={<Share2 className="w-4 h-4 text-emerald-400" />} />
            </div>
          </div>
          <div className="flex gap-3 mt-6 pt-6" style={{ borderTop: "1px solid var(--surface-border)" }}>
            <Button variant="primary" icon={<ArrowUpRight className="w-4 h-4" />}>Upgrade Plan</Button>
            <Button variant="secondary">Manage Subscription</Button>
          </div>
        </GlassCard>
      </motion.div>

      {/* Pricing Toggle */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }} className="flex items-center justify-center gap-4 mb-8">
        <span className="text-sm font-medium transition-colors" style={{ color: !annual ? "var(--page-heading)" : "var(--page-text-secondary)" }}>Monthly</span>
        <button
          onClick={() => setAnnual(!annual)}
          className={cn("relative w-14 h-7 rounded-full transition-colors duration-300 cursor-pointer", annual && "bg-gradient-to-r from-purple-600 to-blue-600")}
          style={!annual ? { backgroundColor: "var(--sidebar-hover-bg)" } : undefined}
        >
          <div className={cn("absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-lg transition-transform duration-300", annual ? "translate-x-[30px]" : "translate-x-[2px]")} />
        </button>
        <span className="text-sm font-medium transition-colors" style={{ color: annual ? "var(--page-heading)" : "var(--page-text-secondary)" }}>
          Annual
          <Badge variant="success" size="sm" className="ml-2">Save 20%</Badge>
        </span>
      </motion.div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {plans.map((plan, idx) => {
          const isCurrent = plan.id === currentPlanId;
          const Icon = plan.icon;
          const price = annual ? plan.annualPrice : plan.monthlyPrice;

          return (
            <motion.div key={plan.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + idx * 0.1, duration: 0.5 }}>
              <GlassCard className={cn("relative h-full", isCurrent && "!border-purple-500/30 !shadow-lg !shadow-purple-500/10", plan.popular && "ring-1 ring-purple-500/30")}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge variant="info" className="!bg-gradient-to-r !from-purple-600 !to-blue-600 !border-0 !text-white !shadow-lg !shadow-purple-500/30">
                      <Sparkles className="w-3 h-3 mr-1" /> Most Popular
                    </Badge>
                  </div>
                )}

                <div className="text-center mb-6">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center mx-auto mb-3">
                    <Icon className="w-6 h-6 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-bold" style={{ color: "var(--page-heading)" }}>{plan.name}</h3>
                  <p className="text-xs mt-1" style={{ color: "var(--page-text-secondary)" }}>{plan.description}</p>
                  <div className="mt-4">
                    <span className="text-3xl font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>${price}</span>
                    <span className="text-sm" style={{ color: "var(--page-text-secondary)" }}>/mo</span>
                  </div>
                </div>

                <div className="space-y-3 mb-6">
                  {plan.features.map((feat, fIdx) => (
                    <div key={fIdx} className="flex items-center gap-2.5">
                      <div className={cn("w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0", feat.included && "bg-emerald-500/15")} style={!feat.included ? { backgroundColor: "var(--sidebar-hover-bg)" } : undefined}>
                        {feat.included ? <Check className="w-3 h-3 text-emerald-400" /> : <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--page-text-muted)" }} />}
                      </div>
                      <span className="text-sm" style={{ color: feat.included ? "var(--page-text)" : "var(--page-text-muted)" }}>{feat.text}</span>
                    </div>
                  ))}
                </div>

                <Button variant={isCurrent ? "secondary" : "primary"} fullWidth disabled={isCurrent}>
                  {isCurrent ? "Current Plan" : "Select Plan"}
                </Button>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>

      {/* Payment Method */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6, duration: 0.5 }}>
        <GlassCard className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center">
                <CreditCard className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium" style={{ color: "var(--page-text)" }}>Visa ending in 4242</p>
                  <Badge variant="success" size="sm">Default</Badge>
                </div>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>Expires 12/2027</p>
              </div>
            </div>
            <Button variant="secondary" size="sm">Update Payment Method</Button>
          </div>
        </GlassCard>
      </motion.div>

      {/* Billing History */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7, duration: 0.5 }}>
        <GlassCard>
          <h3 className="text-lg font-semibold mb-5" style={{ color: "var(--page-heading)" }}>Billing History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                  <th className="text-left font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Invoice</th>
                  <th className="text-left font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Date</th>
                  <th className="text-left font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Description</th>
                  <th className="text-right font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Amount</th>
                  <th className="text-center font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Status</th>
                  <th className="text-center font-medium py-3" />
                </tr>
              </thead>
              <tbody>
                {mockInvoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-[var(--sidebar-hover-bg)] transition-colors" style={{ borderBottom: "1px solid var(--surface-border)" }}>
                    <td className="py-3.5 pr-4 font-mono text-xs" style={{ color: "var(--page-text)" }}>{inv.id}</td>
                    <td className="py-3.5 pr-4" style={{ color: "var(--page-text)" }}>{inv.date}</td>
                    <td className="py-3.5 pr-4" style={{ color: "var(--page-text)" }}>{inv.description}</td>
                    <td className="py-3.5 pr-4 text-right font-medium tabular-nums" style={{ color: "var(--page-text)" }}>${inv.amount.toFixed(2)}</td>
                    <td className="py-3.5 pr-4 text-center">
                      <Badge variant={inv.status === "paid" ? "success" : inv.status === "pending" ? "warning" : "danger"} size="sm">
                        {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                      </Badge>
                    </td>
                    <td className="py-3.5 text-center">
                      <button className="p-1.5 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-colors cursor-pointer" style={{ color: "var(--page-text-secondary)" }}>
                        <Download className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </motion.div>
    </DashboardLayout>
  );
}
