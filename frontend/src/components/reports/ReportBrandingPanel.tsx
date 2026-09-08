/**
 * White-label settings and the automatic-report toggle.
 *
 * The panel is deliberately honest about the plan boundary. Branding is
 * *stored* whatever the plan says — someone evaluating the feature should be
 * able to fill it in before they upgrade — but the page shows which values a
 * report would actually use today, so a workspace without the entitlement is
 * never left wondering why its PDF is still purple.
 */
import { useCallback, useEffect, useState } from "react";
import { Info, Lock, Save } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { detailFrom } from "@/lib/scheduling";
import { reportsApi, type Branding, type BrandingState } from "@/lib/reports";

const CADENCES = [
  { value: "off", label: "Off" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
] as const;

export function ReportBrandingPanel({ accountId }: { accountId: string }) {
  const [state, setState] = useState<BrandingState | null>(null);
  const [draft, setDraft] = useState<Partial<Branding>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await reportsApi.branding(accountId);
      setState(data);
      setDraft(data.branding);
    } catch (err) {
      showError(detailFrom(err, "Could not load branding settings."));
    }
  }, [accountId]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await reportsApi.saveBranding(accountId, draft);
      showSuccess("Branding saved.");
      await load();
    } catch (err) {
      showError(detailFrom(err, "Could not save branding."));
    } finally {
      setSaving(false);
    }
  };

  const setCadence = async (cadence: "off" | "weekly" | "monthly") => {
    try {
      await reportsApi.saveCadence(accountId, cadence);
      setState((prev) => (prev ? { ...prev, cadence } : prev));
      showSuccess(
        cadence === "off"
          ? "Automatic reports switched off."
          : `A ${cadence} report will be generated automatically.`
      );
    } catch (err) {
      showError(detailFrom(err, "Could not change the schedule."));
    }
  };

  if (!state) {
    return (
      <GlassCard>
        <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
          Loading…
        </p>
      </GlassCard>
    );
  }

  const field = (key: keyof Branding, label: string, type = "text") => (
    <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
      {label}
      <input
        type={type}
        value={(draft[key] as string) ?? ""}
        onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
        className={cn("mt-1 w-full rounded-lg px-2.5 py-1.5 text-sm", type === "color" && "h-9 p-1")}
        style={{
          backgroundColor: "var(--input-bg)",
          color: "var(--page-text)",
          border: "1px solid var(--surface-border)",
        }}
      />
    </label>
  );

  return (
    <GlassCard>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Report branding
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
            Applied to the PDF and the workbook a client receives.
          </p>
        </div>
        <Button variant="primary" size="sm" loading={saving}
                icon={<Save className="h-3.5 w-3.5" />} onClick={save}>
          Save
        </Button>
      </div>

      {!state.white_label && (
        <div
          className="mb-4 flex items-start gap-2 rounded-xl px-3 py-2 text-xs"
          style={{
            backgroundColor: "rgba(245,158,11,0.10)",
            border: "1px solid rgba(245,158,11,0.28)",
            color: "var(--page-text)",
          }}
        >
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#f59e0b" }} />
          <span>
            White-label is not on your plan, so reports use the default branding.
            You can still set these up — they will apply as soon as the plan
            includes it.
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {field("company_name", "Company name")}
        {field("logo_url", "Logo URL (https)")}
        {field("footer_note", "Footer note")}
        {field("primary_color", "Primary colour", "color")}
        {field("accent_color", "Accent colour", "color")}
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--surface-border)" }}>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>
            Automatic reports
          </span>
          <div className="flex gap-1.5">
            {CADENCES.map((option) => (
              <button
                key={option.value}
                onClick={() => setCadence(option.value)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs transition-colors",
                  state.cadence === option.value && "bg-purple-500/20 text-purple-300"
                )}
                style={
                  state.cadence === option.value
                    ? undefined
                    : { color: "var(--page-text-secondary)", backgroundColor: "var(--sidebar-hover-bg)" }
                }
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="flex items-center gap-1.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
            <Info className="h-3.5 w-3.5" />
            Generated once the period has finished, and only once per period.
          </p>
        </div>
      </div>
    </GlassCard>
  );
}

export default ReportBrandingPanel;
