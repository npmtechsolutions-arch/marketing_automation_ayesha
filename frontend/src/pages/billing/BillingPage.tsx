import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Building2,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { showError, showSuccess } from "@/components/ui/Toast";
import api, { getAccountId } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── API types ───────────────────────────────────────────────────────

interface UsageMetric {
  used: number;
  limit: number; // -1 = unlimited
}

interface PlanSummary {
  id: string;
  name: string;
  rank: number;
  monthly_price: number;
  annual_price: number;
  posts: number;
  members: number;
  platforms: number;
  purchasable: boolean;
  contact_sales: boolean;
}

interface BillingInfo {
  subscription_tier: string;
  subscription_status: string;
  current_period_end: string | null;
  stripe_customer_id: string | null;
  cancel_at_period_end: boolean;
  stripe_enabled: boolean;
  manual_plan_change_enabled: boolean;
  usage: Record<string, UsageMetric>;
  plans: PlanSummary[];
}

interface Invoice {
  id: string;
  amount: number;
  currency: string;
  status: string;
  created: string;
  pdf_url: string | null;
}

// ── Per-tier presentation (copy that has no place in the database) ──

interface PlanCopy {
  icon: React.ElementType;
  description: string;
  popular?: boolean;
  highlights: { text: string; included: boolean }[];
}

const PLAN_COPY: Record<string, PlanCopy> = {
  free: {
    icon: Sparkles,
    description: "Try MarketEngine with a single workspace",
    highlights: [
      { text: "Content calendar & scheduling", included: true },
      { text: "Basic analytics", included: true },
      { text: "AI content suggestions", included: false },
      { text: "Priority support", included: false },
    ],
  },
  starter: {
    icon: Zap,
    description: "Perfect for solopreneurs and small teams getting started",
    highlights: [
      { text: "Basic analytics", included: true },
      { text: "AI content suggestions", included: true },
      { text: "Email support", included: true },
      { text: "Advanced AI strategies", included: false },
      { text: "White-label reports", included: false },
    ],
  },
  growth: {
    icon: Rocket,
    popular: true,
    description: "For growing teams that need more power and flexibility",
    highlights: [
      { text: "Advanced analytics", included: true },
      { text: "AI content generation", included: true },
      { text: "AI strategy recommendations", included: true },
      { text: "Campaign management", included: true },
      { text: "White-label reports", included: false },
    ],
  },
  pro: {
    icon: Crown,
    description: "For agencies and enterprises with advanced needs",
    highlights: [
      { text: "Custom analytics dashboards", included: true },
      { text: "Advanced AI content suite", included: true },
      { text: "Custom AI brand voice", included: true },
      { text: "White-label reports", included: true },
      { text: "Dedicated account manager", included: true },
    ],
  },
  enterprise: {
    icon: Building2,
    description: "Custom limits, security review and onboarding",
    highlights: [
      { text: "Everything in Pro", included: true },
      { text: "SSO & advanced security", included: true },
      { text: "Custom integrations", included: true },
      { text: "SLA & dedicated support", included: true },
    ],
  },
};

const STATUS_BADGE: Record<string, { label: string; variant: "success" | "info" | "warning" | "danger" }> = {
  active: { label: "Active", variant: "success" },
  trialing: { label: "Trial", variant: "info" },
  past_due: { label: "Past due", variant: "warning" },
  cancelled: { label: "Cancelled", variant: "danger" },
};

// ── Helpers ─────────────────────────────────────────────────────────

const fmtLimit = (value: number) => (value < 0 ? "Unlimited" : value.toLocaleString());

const fmtDate = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
    : null;

const errorDetail = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
};

function UsageMeter({ label, used, limit, icon }: { label: string; used: number; limit: number; icon: React.ReactNode }) {
  const isUnlimited = limit < 0;
  const pct = isUnlimited || limit === 0 ? 0 : Math.min(100, (used / limit) * 100);
  const isHigh = !isUnlimited && pct > 80;

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

// ── Component ───────────────────────────────────────────────────────

export default function BillingPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [annual, setAnnual] = useState(false);
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingPlan, setPendingPlan] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const plansRef = useRef<HTMLDivElement>(null);

  // ── Load subscription + invoices ─────────────────────────────────
  const loadBilling = useCallback(async () => {
    setLoading(true);
    setError(null);
    const accountId = await getAccountId();
    if (!accountId) {
      setLoading(false);
      setError("Could not determine your account. Please refresh the page.");
      return;
    }
    try {
      const res: any = await api.get(`/accounts/${accountId}/billing/`);
      setInfo(res.data ?? res);
    } catch (err: any) {
      setError(errorDetail(err, "Failed to load your subscription."));
      setLoading(false);
      return;
    }
    try {
      const res: any = await api.get(`/accounts/${accountId}/billing/invoices`);
      const payload = res.data ?? res;
      setInvoices(Array.isArray(payload) ? payload : []);
    } catch {
      setInvoices([]); // Invoices are optional — never block the page on them.
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadBilling();
  }, [loadBilling]);

  // Returning from Stripe Checkout.
  useEffect(() => {
    const checkout = searchParams.get("checkout");
    if (!checkout) return;
    if (checkout === "success") {
      showSuccess("Payment received. Your new plan is being activated.");
    } else if (checkout === "cancelled") {
      showError("Checkout was cancelled — your plan is unchanged.");
    }
    searchParams.delete("checkout");
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const currentTier = info?.subscription_tier ?? "free";
  const plans = useMemo(
    () =>
      (info?.plans ?? []).filter(
        // Enterprise is sales-led: only show it once the account is actually on it.
        (p) => !p.contact_sales || p.id === currentTier
      ),
    [info?.plans, currentTier]
  );
  const currentPlan = info?.plans.find((p) => p.id === currentTier) ?? null;
  const currentRank = currentPlan?.rank ?? 0;
  const isTopTier = plans.length > 0 && currentRank >= Math.max(...plans.map((p) => p.rank));

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const accountId = await getAccountId();
      const res: any = await api.post(`/accounts/${accountId}/billing/portal`, {});
      const payload = res.data ?? res;
      if (payload.portal_url) {
        window.location.href = payload.portal_url;
        return;
      }
      showError("Could not open the billing portal.");
    } catch (err: any) {
      showError(errorDetail(err, "Could not open the billing portal."));
    } finally {
      setPortalLoading(false);
    }
  };

  const handleSelectPlan = async (plan: PlanSummary) => {
    if (!info || plan.id === currentTier) return;

    if (plan.contact_sales) {
      navigate("/help");
      return;
    }

    setPendingPlan(plan.id);
    try {
      const accountId = await getAccountId();
      if (!accountId) {
        showError("Could not determine your account. Please refresh the page.");
        return;
      }

      // An upgrade to a tier Stripe actually sells goes through Checkout.
      if (info.stripe_enabled && plan.purchasable && plan.rank > currentRank) {
        const origin = window.location.origin;
        const res: any = await api.post(`/accounts/${accountId}/billing/checkout`, {
          tier: plan.id,
          success_url: `${origin}/billing?checkout=success`,
          cancel_url: `${origin}/billing?checkout=cancelled`,
        });
        const payload = res.data ?? res;
        if (payload.checkout_url) {
          window.location.href = payload.checkout_url;
          return;
        }
        showError("Could not start checkout. Please try again.");
        return;
      }

      // Downgrades and cancellations act on the existing Stripe subscription,
      // so they belong in the customer portal rather than a new checkout.
      if (info.stripe_enabled && info.stripe_customer_id && plan.rank < currentRank) {
        await openPortal();
        return;
      }

      // No payment provider in play — the backend decides whether a direct
      // switch is permitted and answers with the refreshed subscription.
      if (info.manual_plan_change_enabled) {
        const res: any = await api.post(`/accounts/${accountId}/billing/change-plan`, {
          tier: plan.id,
        });
        setInfo(res.data ?? res);
        showSuccess(`You are now on the ${plan.name} plan.`);
        return;
      }

      showError(
        info.stripe_enabled
          ? `The ${plan.name} plan has no Stripe price configured yet. Please contact support.`
          : "Plan changes are unavailable until billing is configured."
      );
    } catch (err: any) {
      showError(errorDetail(err, `Could not switch to the ${plan.name} plan.`));
    } finally {
      setPendingPlan(null);
    }
  };

  // ── Loading / error ───────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
          <span className="ml-3" style={{ color: "var(--page-text-secondary)" }}>Loading your subscription…</span>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !info || !currentPlan) {
    return (
      <DashboardLayout>
        <GlassCard className="border-red-500/20">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">{error ?? "Your subscription could not be loaded."}</p>
            <Button variant="ghost" size="sm" onClick={loadBilling} className="ml-auto">
              <RefreshCw className="w-4 h-4 mr-1" /> Retry
            </Button>
          </div>
        </GlassCard>
      </DashboardLayout>
    );
  }

  const CurrentIcon = (PLAN_COPY[currentTier] ?? PLAN_COPY.free).icon;
  const statusBadge = STATUS_BADGE[info.subscription_status] ?? { label: info.subscription_status, variant: "info" as const };
  const renewalDate = fmtDate(info.current_period_end);
  const usage = info.usage ?? {};

  // A workspace can carry limits that were set by hand and no longer match its
  // tier's defaults. Those stored limits are what the backend enforces, so they
  // are what the current plan's card has to show.
  const accountLimits = {
    posts: usage.posts?.limit ?? currentPlan.posts,
    members: usage.members?.limit ?? currentPlan.members,
    platforms: usage.platforms?.limit ?? currentPlan.platforms,
  };
  const hasCustomLimits =
    accountLimits.posts !== currentPlan.posts ||
    accountLimits.members !== currentPlan.members ||
    accountLimits.platforms !== currentPlan.platforms;

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
                  <CurrentIcon className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-xl font-bold" style={{ color: "var(--page-heading)" }}>{currentPlan.name} Plan</h2>
                    <Badge variant="info">Current</Badge>
                    <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
                    {hasCustomLimits && <Badge variant="default">Custom limits</Badge>}
                  </div>
                  <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                    {(PLAN_COPY[currentTier] ?? PLAN_COPY.free).description}
                  </p>
                </div>
              </div>
              <div className="mt-4">
                <span className="text-4xl font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>
                  ${annual ? currentPlan.annual_price : currentPlan.monthly_price}
                </span>
                <span className="text-sm" style={{ color: "var(--page-text-secondary)" }}>/month</span>
              </div>
              <p className="text-xs mt-1" style={{ color: "var(--page-text-muted)" }}>
                <Calendar className="w-3.5 h-3.5 inline mr-1" />
                {info.cancel_at_period_end && renewalDate
                  ? `Cancels on ${renewalDate}`
                  : renewalDate
                    ? `Next renewal: ${renewalDate}`
                    : currentPlan.monthly_price === 0
                      ? "No billing on this plan"
                      : "No renewal date on file"}
              </p>
            </div>
            <div className="flex-1 space-y-4">
              <UsageMeter label="Posts this month" used={usage.posts?.used ?? 0} limit={usage.posts?.limit ?? currentPlan.posts} icon={<FileText className="w-4 h-4 text-purple-400" />} />
              <UsageMeter label="Team Members" used={usage.members?.used ?? 0} limit={usage.members?.limit ?? currentPlan.members} icon={<Users className="w-4 h-4 text-blue-400" />} />
              <UsageMeter label="Platforms" used={usage.platforms?.used ?? 0} limit={usage.platforms?.limit ?? currentPlan.platforms} icon={<Share2 className="w-4 h-4 text-emerald-400" />} />
            </div>
          </div>
          <div className="flex flex-wrap gap-3 mt-6 pt-6" style={{ borderTop: "1px solid var(--surface-border)" }}>
            {!isTopTier && (
              <Button
                variant="primary"
                icon={<ArrowUpRight className="w-4 h-4" />}
                onClick={() => plansRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
              >
                Upgrade Plan
              </Button>
            )}
            {info.stripe_enabled && info.stripe_customer_id && (
              <Button variant="secondary" loading={portalLoading} onClick={openPortal}>
                Manage Subscription
              </Button>
            )}
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
      <div ref={plansRef} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-4">
        {plans.map((plan, idx) => {
          const copy = PLAN_COPY[plan.id] ?? PLAN_COPY.free;
          const Icon = copy.icon;
          const isCurrent = plan.id === currentTier;
          const isUpgrade = plan.rank > currentRank;
          const price = annual ? plan.annual_price : plan.monthly_price;
          const isPending = pendingPlan === plan.id;

          // On your own card, show what your workspace is actually allowed —
          // every other card advertises the tier's standard allowance.
          const showAccountLimits = isCurrent && hasCustomLimits;
          const limits = showAccountLimits
            ? accountLimits
            : { posts: plan.posts, members: plan.members, platforms: plan.platforms };

          const label = isCurrent
            ? "Current Plan"
            : plan.contact_sales
              ? "Contact Sales"
              : isUpgrade
                ? "Upgrade Plan"
                : plan.id === "free"
                  ? "Cancel Subscription"
                  : "Downgrade Plan";

          return (
            <motion.div key={plan.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + idx * 0.1, duration: 0.5 }}>
              <GlassCard className={cn("relative h-full flex flex-col", isCurrent && "!border-purple-500/40 !shadow-lg !shadow-purple-500/10", !isCurrent && copy.popular && "ring-1 ring-purple-500/30")}>
                {isCurrent ? (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge variant="success" className="!shadow-lg">
                      <Check className="w-3 h-3 mr-1" /> Your Plan
                    </Badge>
                  </div>
                ) : copy.popular ? (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge variant="info" className="!bg-gradient-to-r !from-purple-600 !to-blue-600 !border-0 !text-white !shadow-lg !shadow-purple-500/30">
                      <Sparkles className="w-3 h-3 mr-1" /> Most Popular
                    </Badge>
                  </div>
                ) : null}

                <div className="text-center mb-6">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center mx-auto mb-3">
                    <Icon className="w-6 h-6 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-bold" style={{ color: "var(--page-heading)" }}>{plan.name}</h3>
                  <p className="text-xs mt-1" style={{ color: "var(--page-text-secondary)" }}>{copy.description}</p>
                  <div className="mt-4">
                    {plan.contact_sales ? (
                      <span className="text-3xl font-bold" style={{ color: "var(--page-heading)" }}>Custom</span>
                    ) : (
                      <>
                        <span className="text-3xl font-bold tabular-nums" style={{ color: "var(--page-heading)" }}>${price}</span>
                        <span className="text-sm" style={{ color: "var(--page-text-secondary)" }}>/mo</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="space-y-3 mb-6 flex-1">
                  {[
                    { text: `${fmtLimit(limits.posts)} posts/month`, included: true },
                    { text: `${fmtLimit(limits.members)} team members`, included: true },
                    { text: `${fmtLimit(limits.platforms)} social platforms`, included: true },
                    ...copy.highlights,
                  ].map((feat, fIdx) => (
                    <div key={fIdx} className="flex items-center gap-2.5">
                      <div className={cn("w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0", feat.included && "bg-emerald-500/15")} style={!feat.included ? { backgroundColor: "var(--sidebar-hover-bg)" } : undefined}>
                        {feat.included ? <Check className="w-3 h-3 text-emerald-400" /> : <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--page-text-muted)" }} />}
                      </div>
                      <span className="text-sm" style={{ color: feat.included ? "var(--page-text)" : "var(--page-text-muted)" }}>{feat.text}</span>
                    </div>
                  ))}
                  {showAccountLimits && (
                    <p className="text-xs pt-1" style={{ color: "var(--page-text-muted)" }}>
                      Custom limits for your workspace. The standard {plan.name} plan includes{" "}
                      {fmtLimit(plan.posts)} posts, {fmtLimit(plan.members)} members and{" "}
                      {fmtLimit(plan.platforms)} platforms.
                    </p>
                  )}
                </div>

                <Button
                  variant={isCurrent ? "secondary" : isUpgrade ? "primary" : "ghost"}
                  fullWidth
                  disabled={isCurrent || (pendingPlan !== null && !isPending)}
                  loading={isPending}
                  onClick={() => handleSelectPlan(plan)}
                >
                  {label}
                </Button>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>

      <p className="text-xs text-center mb-8" style={{ color: "var(--page-text-muted)" }}>
        {info.stripe_enabled && plans.some((p) => p.purchasable)
          ? "Plan changes are processed securely through Stripe. Annual pricing is shown as the effective monthly rate."
          : info.manual_plan_change_enabled
            ? "Payments are not configured on this environment — plan changes apply immediately without charge."
            : "Online plan changes are unavailable until billing is fully configured. Contact support to change your plan."}
      </p>

      {/* Payment Method */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6, duration: 0.5 }}>
        <GlassCard className="mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center">
                <CreditCard className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="font-medium" style={{ color: "var(--page-text)" }}>
                  {info.stripe_customer_id ? "Card on file" : "No payment method"}
                </p>
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                  {info.stripe_customer_id
                    ? "Managed securely in the Stripe billing portal"
                    : "Added when you subscribe to a paid plan"}
                </p>
              </div>
            </div>
            {info.stripe_enabled && info.stripe_customer_id && (
              <Button variant="secondary" size="sm" loading={portalLoading} onClick={openPortal}>
                Update Payment Method
              </Button>
            )}
          </div>
        </GlassCard>
      </motion.div>

      {/* Billing History */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7, duration: 0.5 }}>
        <GlassCard>
          <h3 className="text-lg font-semibold mb-5" style={{ color: "var(--page-heading)" }}>Billing History</h3>
          {invoices.length === 0 ? (
            <p className="text-sm py-6 text-center" style={{ color: "var(--page-text-secondary)" }}>
              No invoices yet. Paid invoices appear here once you subscribe.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                    <th className="text-left font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Invoice</th>
                    <th className="text-left font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Date</th>
                    <th className="text-right font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Amount</th>
                    <th className="text-center font-medium py-3 pr-4" style={{ color: "var(--page-text-secondary)" }}>Status</th>
                    <th className="text-center font-medium py-3" />
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-[var(--sidebar-hover-bg)] transition-colors" style={{ borderBottom: "1px solid var(--surface-border)" }}>
                      <td className="py-3.5 pr-4 font-mono text-xs" style={{ color: "var(--page-text)" }}>{inv.id}</td>
                      <td className="py-3.5 pr-4" style={{ color: "var(--page-text)" }}>{fmtDate(inv.created)}</td>
                      <td className="py-3.5 pr-4 text-right font-medium tabular-nums" style={{ color: "var(--page-text)" }}>
                        {inv.currency?.toUpperCase() === "USD" ? "$" : ""}{inv.amount.toFixed(2)}
                      </td>
                      <td className="py-3.5 pr-4 text-center">
                        <Badge variant={inv.status === "paid" ? "success" : inv.status === "open" ? "warning" : "danger"} size="sm">
                          {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3.5 text-center">
                        {inv.pdf_url && (
                          <a
                            href={inv.pdf_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex p-1.5 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-colors cursor-pointer"
                            style={{ color: "var(--page-text-secondary)" }}
                          >
                            <Download className="w-4 h-4" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      </motion.div>
    </DashboardLayout>
  );
}
