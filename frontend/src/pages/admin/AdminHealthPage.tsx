/**
 * Connected-account health, across every customer.
 *
 * The strip added in 1.9 tells one workspace its connection is broken. This is
 * the other direction: which customers are broken right now, so support can
 * reach them before a scheduled post fails and the slot is gone.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, HelpCircle, RefreshCw } from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { showError } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { adminApi, type ConnectionHealth } from "@/lib/admin";
import { platformColor, SERIES } from "../analytics/chart";

const STATES: { key: string; label: string; icon: React.ReactNode; color: string }[] = [
  // Keys are the AccountHealth enum values, not prose: "connected", not
  // "healthy". A mismatch here renders every count as zero and nothing
  // errors -- the page just quietly reports a clean bill of health.
  { key: "connected", label: "Connected", icon: <CheckCircle2 className="h-5 w-5" />, color: SERIES.emerald },
  { key: "expiring", label: "Expiring", icon: <Clock className="h-5 w-5" />, color: SERIES.amber },
  { key: "failed", label: "Failed", icon: <AlertTriangle className="h-5 w-5" />, color: SERIES.rose },
  { key: "unknown", label: "Unknown", icon: <HelpCircle className="h-5 w-5" />, color: SERIES.muted },
];

export default function AdminHealthPage() {
  const [data, setData] = useState<ConnectionHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await adminApi.connectionHealth());
    } catch {
      showError("Could not load connection health.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Connection health
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Every connected social account across all customers.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="rounded-xl p-2 disabled:opacity-50"
            style={{
              backgroundColor: "var(--sidebar-hover-bg)",
              color: "var(--page-text-secondary)",
            }}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {STATES.map((state) => (
            <StatCard
              key={state.key}
              label={state.label}
              // Zero, not a dash: the endpoint returns every state explicitly,
              // so a zero here means "none" rather than "not measured".
              value={String(data?.counts?.[state.key] ?? 0)}
              icon={<span style={{ color: state.color }}>{state.icon}</span>}
              loading={loading && !data}
            />
          ))}
        </div>

        <GlassCard>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              Failed connections
            </h3>
            <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              Longest-broken first — a connection down for a week matters more than
              one that broke this morning.
            </p>
          </div>

          {loading && !data ? (
            <Skeleton variant="card" height="220px" />
          ) : (data?.failed.length ?? 0) === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-7 w-7" />}
              title="Nothing is failing"
              description="Every connected account is healthy or expiring. Nobody needs contacting."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead>
                  <tr style={{ color: "var(--page-text-muted)" }}>
                    <th className="px-3 py-2 text-left font-medium">Organization</th>
                    <th className="px-3 py-2 text-left font-medium">Workspace</th>
                    <th className="px-3 py-2 text-left font-medium">Plan</th>
                    <th className="px-3 py-2 text-left font-medium">Connection</th>
                    <th className="px-3 py-2 text-left font-medium">Reason</th>
                    <th className="px-3 py-2 text-left font-medium">Since</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.failed.map((row) => (
                    <tr key={row.id} style={{ borderTop: "1px solid var(--surface-border)" }}>
                      <td className="px-3 py-3" style={{ color: "var(--page-text)" }}>
                        {row.organization ?? "—"}
                      </td>
                      <td className="px-3 py-3" style={{ color: "var(--page-text-secondary)" }}>
                        {row.workspace}
                      </td>
                      <td className="px-3 py-3 capitalize" style={{ color: "var(--page-text-secondary)" }}>
                        {row.plan ?? "—"}
                      </td>
                      <td className="px-3 py-3">
                        <span className="flex items-center gap-2" style={{ color: "var(--page-text)" }}>
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: platformColor(row.platform) }}
                          />
                          {row.account_name}
                        </span>
                      </td>
                      <td
                        className="max-w-[260px] truncate px-3 py-3"
                        style={{ color: SERIES.rose }}
                        title={row.detail ?? ""}
                      >
                        {row.detail ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3" style={{ color: "var(--page-text-muted)" }}>
                        {row.checked_at ? row.checked_at.slice(0, 10) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      </div>
    </DashboardLayout>
  );
}
