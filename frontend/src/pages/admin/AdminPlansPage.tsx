import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  SlidersHorizontal,
  Check,
  X,
  Infinity as InfinityIcon,
  Loader2,
  AlertCircle,
  Plus,
  Pencil,
  Tag,
  Archive,
  RefreshCw,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { showError, showSuccess } from "@/components/ui/Toast";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types -- mirror app/api/v1/endpoints/admin.py
// ---------------------------------------------------------------------------

interface Feature {
  key: string;
  name: string;
  description: string | null;
  unit: string;
  is_metered: boolean;
  sort_order: number;
}

interface PlanFeature {
  feature_key: string;
  name: string;
  unit: string;
  /** null is unlimited; 0 means the plan does not include the feature. */
  limit_value: number | null;
  unlimited: boolean;
}

interface Plan {
  id: string;
  key: string;
  name: string;
  stripe_price_id: string | null;
  price_monthly: number;
  is_active: boolean;
  sort_order: number;
  features: PlanFeature[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const errorDetail = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
};

const fmtBytes = (value: number) => {
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let n = value / 1024;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n % 1 === 0 ? n : n.toFixed(1)} ${units[i]}`;
};

/** What the operator types, in both directions.
 *
 * An empty box is unlimited. That has to be unambiguous: the old code used -1
 * for unlimited and 99999 as a stand-in for "effectively unlimited", and the
 * two were impossible to tell apart once written down. */
const toInput = (value: number | null) => (value === null ? "" : String(value));

const fromInput = (raw: string): number | null | undefined => {
  const trimmed = raw.trim();
  if (trimmed === "") return null; // unlimited
  if (!/^\d+$/.test(trimmed)) return undefined; // invalid
  return Number(trimmed);
};

const describeLimit = (pf: PlanFeature) => {
  if (pf.unit === "boolean") return pf.limit_value ? "Included" : "Not included";
  if (pf.limit_value === null) return "Unlimited";
  if (pf.unit === "bytes") return fmtBytes(pf.limit_value);
  return pf.limit_value.toLocaleString();
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AdminPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  // The plan's own fields, edited separately from its limits: PATCH /plans/{id}
  // and PUT /plans/{id}/limits are different endpoints with different audit
  // entries, and price changes move MRR while limit changes do not.
  const [detailsPlanId, setDetailsPlanId] = useState<string | null>(null);
  const [detailsDraft, setDetailsDraft] = useState({ name: "", price_monthly: "0", stripe_price_id: "" });

  const [creating, setCreating] = useState(false);
  const [newPlan, setNewPlan] = useState({ key: "", name: "", price_monthly: "0" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [planRes, featureRes] = await Promise.all([
        api.get("/admin/plans"),
        api.get("/admin/features"),
      ]);
      setPlans((planRes.data ?? planRes) as Plan[]);
      setFeatures((featureRes.data ?? featureRes) as Feature[]);
    } catch (err: any) {
      setError(errorDetail(err, "Failed to load plans."));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const orderedFeatures = useMemo(
    () => [...features].sort((a, b) => a.sort_order - b.sort_order || a.key.localeCompare(b.key)),
    [features]
  );

  const startEditing = (plan: Plan) => {
    const next: Record<string, string> = {};
    for (const f of orderedFeatures) {
      const pf = plan.features.find((x) => x.feature_key === f.key);
      next[f.key] = toInput(pf ? pf.limit_value : 0);
    }
    setDraft(next);
    setEditingPlanId(plan.id);
  };

  const saveLimits = async (plan: Plan) => {
    const limits: Record<string, number | null> = {};
    for (const [key, raw] of Object.entries(draft)) {
      const parsed = fromInput(raw);
      if (parsed === undefined) {
        showError(`"${raw}" is not a valid limit for ${key}. Use a whole number, or leave it empty for unlimited.`);
        return;
      }
      limits[key] = parsed;
    }

    setSaving(true);
    try {
      const res: any = await api.put(`/admin/plans/${plan.id}/limits`, { limits });
      const updated = (res.data ?? res) as Plan;
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setEditingPlanId(null);
      showSuccess(`${plan.name} limits updated. They take effect immediately.`);
    } catch (err: any) {
      showError(errorDetail(err, "Could not save the limits."));
    }
    setSaving(false);
  };

  const startEditingDetails = (plan: Plan) => {
    setDetailsDraft({
      name: plan.name,
      price_monthly: String(plan.price_monthly ?? 0),
      stripe_price_id: plan.stripe_price_id ?? "",
    });
    setDetailsPlanId(plan.id);
  };

  const saveDetails = async (plan: Plan) => {
    const price = Number(detailsDraft.price_monthly);
    if (!detailsDraft.name.trim()) {
      showError("A plan needs a name.");
      return;
    }
    if (!Number.isFinite(price) || price < 0) {
      showError("Price must be a number of zero or more.");
      return;
    }
    setSaving(true);
    try {
      const res: any = await api.patch(`/admin/plans/${plan.id}`, {
        name: detailsDraft.name.trim(),
        price_monthly: price,
        // Empty means "not sold through Stripe", which is null rather than "".
        stripe_price_id: detailsDraft.stripe_price_id.trim() || null,
      });
      const updated = (res.data ?? res) as Plan;
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setDetailsPlanId(null);
      showSuccess(`${updated.name} updated. Revenue reporting uses the new price immediately.`);
    } catch (err: any) {
      showError(errorDetail(err, "Could not update the plan."));
    }
    setSaving(false);
  };

  const createPlan = async () => {
    if (!newPlan.key.trim() || !newPlan.name.trim()) {
      showError("A plan needs both a key and a name.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/admin/plans", {
        key: newPlan.key.trim(),
        name: newPlan.name.trim(),
        price_monthly: newPlan.price_monthly || "0",
      });
      setCreating(false);
      setNewPlan({ key: "", name: "", price_monthly: "0" });
      showSuccess("Plan created. Every feature starts at 0 — set its limits next.");
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not create the plan."));
    }
    setSaving(false);
  };

  const retirePlan = async (plan: Plan) => {
    if (!window.confirm(`Retire "${plan.name}"? Existing subscribers keep their limits; the plan stops being offered.`)) {
      return;
    }
    try {
      await api.delete(`/admin/plans/${plan.id}`);
      showSuccess(`${plan.name} retired.`);
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not retire the plan."));
    }
  };

  // -- render ---------------------------------------------------------------

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--page-text-secondary)" }} />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: "var(--page-heading)" }}>
              <SlidersHorizontal className="w-6 h-6" />
              Plans &amp; Limits
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--page-text-secondary)" }}>
              What each plan allows. Changes apply to every organization on that plan straight away — no deploy.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={load}>
              Refresh
            </Button>
            <Button variant="primary" icon={<Plus className="w-4 h-4" />} onClick={() => setCreating((v) => !v)}>
              New plan
            </Button>
          </div>
        </div>

        {error && (
          <GlassCard className="p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="text-sm" style={{ color: "var(--page-text)" }}>{error}</span>
          </GlassCard>
        )}

        {creating && (
          <GlassCard className="p-6 space-y-4">
            <h2 className="font-semibold" style={{ color: "var(--page-heading)" }}>New plan</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <Input
                label="Key"
                placeholder="agency"
                value={newPlan.key}
                onChange={(e) => setNewPlan({ ...newPlan, key: e.target.value })}
              />
              <Input
                label="Name"
                placeholder="Agency"
                value={newPlan.name}
                onChange={(e) => setNewPlan({ ...newPlan, name: e.target.value })}
              />
              <Input
                label="Price / month (USD)"
                value={newPlan.price_monthly}
                onChange={(e) => setNewPlan({ ...newPlan, price_monthly: e.target.value })}
              />
            </div>
            <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              The key must match the subscription tier stored on organizations. Every feature starts at 0.
            </p>
            <div className="flex gap-2">
              <Button variant="primary" loading={saving} onClick={createPlan}>Create</Button>
              <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            </div>
          </GlassCard>
        )}

        {plans.map((plan) => {
          const isEditing = editingPlanId === plan.id;
          return (
            <GlassCard key={plan.id} className="p-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
                    {plan.name}
                  </h2>
                  <Badge variant="default">{plan.key}</Badge>
                  {!plan.is_active && <Badge variant="warning">Retired</Badge>}
                  <span className="text-sm tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                    ${plan.price_monthly}/mo
                  </span>
                </div>
                <div className="flex gap-2">
                  {isEditing ? (
                    <>
                      <Button variant="primary" loading={saving} icon={<Check className="w-4 h-4" />} onClick={() => saveLimits(plan)}>
                        Save
                      </Button>
                      <Button variant="ghost" icon={<X className="w-4 h-4" />} onClick={() => setEditingPlanId(null)}>
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="secondary" icon={<Pencil className="w-4 h-4" />} onClick={() => startEditing(plan)}>
                        Edit limits
                      </Button>
                      <Button variant="secondary" icon={<Tag className="w-4 h-4" />} onClick={() => startEditingDetails(plan)}>
                        Edit details
                      </Button>
                      {plan.is_active && (
                        <Button variant="ghost" icon={<Archive className="w-4 h-4" />} onClick={() => retirePlan(plan)}>
                          Retire
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </div>

              {detailsPlanId === plan.id && (
                <div
                  className="mb-5 grid gap-3 rounded-xl p-4 sm:grid-cols-3"
                  style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
                >
                  <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
                    Name
                    <input
                      value={detailsDraft.name}
                      onChange={(e) => setDetailsDraft({ ...detailsDraft, name: e.target.value })}
                      className="mt-1 w-full rounded-lg px-2.5 py-1.5 text-sm"
                      style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                    />
                  </label>
                  <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
                    Price / month (USD)
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={detailsDraft.price_monthly}
                      onChange={(e) => setDetailsDraft({ ...detailsDraft, price_monthly: e.target.value })}
                      className="mt-1 w-full rounded-lg px-2.5 py-1.5 text-sm tabular-nums"
                      style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                    />
                  </label>
                  <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
                    Stripe price ID (blank if not sold online)
                    <input
                      value={detailsDraft.stripe_price_id}
                      onChange={(e) => setDetailsDraft({ ...detailsDraft, stripe_price_id: e.target.value })}
                      placeholder="price_..."
                      className="mt-1 w-full rounded-lg px-2.5 py-1.5 font-mono text-xs"
                      style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                    />
                  </label>
                  <div className="flex items-end gap-2 sm:col-span-3">
                    <Button variant="primary" loading={saving} icon={<Check className="w-4 h-4" />} onClick={() => saveDetails(plan)}>
                      Save details
                    </Button>
                    <Button variant="ghost" icon={<X className="w-4 h-4" />} onClick={() => setDetailsPlanId(null)}>
                      Cancel
                    </Button>
                    <p className="ml-auto text-xs" style={{ color: "var(--page-text-muted)" }}>
                      Changing the price changes what the revenue report shows, for
                      every organization on this plan.
                    </p>
                  </div>
                </div>
              )}

              <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
                {orderedFeatures.map((feature) => {
                  const pf = plan.features.find((x) => x.feature_key === feature.key);
                  const effective: PlanFeature = pf ?? {
                    feature_key: feature.key,
                    name: feature.name,
                    unit: feature.unit,
                    limit_value: 0,
                    unlimited: false,
                  };

                  return (
                    <div
                      key={feature.key}
                      className="flex items-center justify-between gap-3 py-2"
                      style={{ borderBottom: "1px solid var(--surface-border)" }}
                    >
                      <div className="min-w-0">
                        <div className="text-sm truncate" style={{ color: "var(--page-text)" }}>
                          {feature.name}
                        </div>
                        <div className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                          {feature.key}
                          {feature.is_metered && " · resets monthly"}
                        </div>
                      </div>

                      {isEditing ? (
                        feature.unit === "boolean" ? (
                          <select
                            className="text-sm rounded-lg px-2 py-1"
                            style={{
                              backgroundColor: "var(--input-bg)",
                              color: "var(--page-text)",
                              border: "1px solid var(--surface-border)",
                            }}
                            value={draft[feature.key] === "1" ? "1" : "0"}
                            onChange={(e) => setDraft({ ...draft, [feature.key]: e.target.value })}
                          >
                            <option value="0">Not included</option>
                            <option value="1">Included</option>
                          </select>
                        ) : (
                          <input
                            className="w-28 text-sm rounded-lg px-2 py-1 text-right tabular-nums"
                            style={{
                              backgroundColor: "var(--input-bg)",
                              color: "var(--page-text)",
                              border: "1px solid var(--surface-border)",
                            }}
                            placeholder="Unlimited"
                            value={draft[feature.key] ?? ""}
                            onChange={(e) => setDraft({ ...draft, [feature.key]: e.target.value })}
                          />
                        )
                      ) : (
                        <span
                          className={cn(
                            "text-sm font-medium tabular-nums shrink-0",
                            effective.limit_value === 0 && feature.unit !== "boolean" && "opacity-50"
                          )}
                          style={{ color: "var(--page-text)" }}
                        >
                          {effective.limit_value === null ? (
                            <span className="inline-flex items-center gap-1">
                              <InfinityIcon className="w-4 h-4" />
                              Unlimited
                            </span>
                          ) : (
                            describeLimit(effective)
                          )}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              {isEditing && (
                <p className="text-xs mt-4" style={{ color: "var(--page-text-muted)" }}>
                  Leave a box empty for unlimited. 0 means the plan does not include that feature.
                </p>
              )}
            </GlassCard>
          );
        })}
      </motion.div>
    </DashboardLayout>
  );
}
