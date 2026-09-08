/**
 * Reports: request one, watch it build, download it.
 *
 * Generation happens in the worker, so a new report arrives PENDING and the
 * page polls until it is ready. The state lives on the row rather than as a
 * spinner over the page, so the rest of the list stays usable while one builds.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, Clock, Download, FileSpreadsheet, FileText,
  Loader2, Palette, Plus, RefreshCw,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { getAccountIdSync } from "@/lib/api";
import { detailFrom } from "@/lib/scheduling";
import {
  REPORT_TYPES, reportsApi,
  type ReportFormat, type ReportRow, type ReportType,
} from "@/lib/reports";
import ReportBrandingPanel from "@/components/reports/ReportBrandingPanel";

const FORMAT_ICON: Record<ReportFormat, React.ReactNode> = {
  pdf: <FileText className="h-3.5 w-3.5" />,
  csv: <Download className="h-3.5 w-3.5" />,
  xlsx: <FileSpreadsheet className="h-3.5 w-3.5" />,
};

export default function ReportsPage() {
  const accountId = getAccountIdSync();
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [type, setType] = useState<ReportType>("monthly");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [showBranding, setShowBranding] = useState(false);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    if (!accountId) return;
    try {
      const data = await reportsApi.list(accountId);
      setRows(data.reports);
    } catch (err) {
      showError(detailFrom(err, "Could not load reports."));
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => { load(); }, [load]);

  // Poll only while something is actually building, and stop when it settles.
  // An unconditional interval would keep a forgotten tab querying forever.
  useEffect(() => {
    const busy = rows.some((r) => r.status === "pending" || r.status === "generating");
    if (busy && !poll.current) {
      poll.current = setInterval(load, 4000);
    } else if (!busy && poll.current) {
      clearInterval(poll.current);
      poll.current = null;
    }
    return () => {
      if (poll.current) { clearInterval(poll.current); poll.current = null; }
    };
  }, [rows, load]);

  const create = async () => {
    if (!accountId) return;
    if (type === "custom" && (!start || !end)) {
      showError("A custom report needs both a start and an end date.");
      return;
    }
    setCreating(true);
    try {
      await reportsApi.create(accountId, {
        type, ...(type === "custom" ? { start, end } : {}),
      });
      showSuccess("Report queued. It will appear here when it is ready.");
      await load();
    } catch (err) {
      showError(detailFrom(err, "Could not queue that report."));
    } finally {
      setCreating(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Reports
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Performance summaries you can send a client.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" icon={<Palette className="h-3.5 w-3.5" />}
                    onClick={() => setShowBranding((v) => !v)}>
              Branding
            </Button>
            <button onClick={load} className="rounded-xl p-2"
                    style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-secondary)" }}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </button>
          </div>
        </div>

        {showBranding && accountId && <ReportBrandingPanel accountId={accountId} />}

        <GlassCard>
          <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            New report
          </h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-wrap gap-1.5">
              {REPORT_TYPES.map((option) => (
                <button key={option.value} onClick={() => setType(option.value)} title={option.hint}
                  className={cn("rounded-lg px-3 py-1.5 text-xs transition-colors",
                    type === option.value && "bg-purple-500/20 text-purple-300")}
                  style={type === option.value ? undefined
                    : { color: "var(--page-text-secondary)", backgroundColor: "var(--sidebar-hover-bg)" }}>
                  {option.label}
                </button>
              ))}
            </div>

            {type === "custom" && (
              <div className="flex items-center gap-2">
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                  className="rounded-lg px-2.5 py-1.5 text-xs"
                  style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }} />
                <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>to</span>
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                  className="rounded-lg px-2.5 py-1.5 text-xs"
                  style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }} />
              </div>
            )}

            <Button variant="primary" size="sm" loading={creating}
                    icon={<Plus className="h-3.5 w-3.5" />} onClick={create}>
              Generate
            </Button>
            <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              {REPORT_TYPES.find((t) => t.value === type)?.hint}
            </p>
          </div>
        </GlassCard>

        <GlassCard>
          {loading ? (
            <Skeleton variant="card" height="220px" />
          ) : rows.length === 0 ? (
            <EmptyState icon={<FileText className="h-7 w-7" />} title="No reports yet"
              description="Generate one above, or switch on automatic weekly or monthly reports in Branding." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr style={{ color: "var(--page-text-muted)" }}>
                    <th className="px-3 py-2 text-left font-medium">Report</th>
                    <th className="px-3 py-2 text-left font-medium">Period</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                    <th className="px-3 py-2 text-left font-medium">Download</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} style={{ borderTop: "1px solid var(--surface-border)" }}>
                      <td className="px-3 py-3 align-top">
                        <p style={{ color: "var(--page-text)" }}>{row.title}</p>
                        {row.executive_summary && (
                          <p className="mt-0.5 max-w-[420px] truncate text-xs" style={{ color: "var(--page-text-muted)" }}>
                            {row.executive_summary}
                          </p>
                        )}
                        {row.error && (
                          <p className="mt-0.5 flex items-start gap-1 text-xs" style={{ color: "#f59e0b" }}>
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            {row.error}
                          </p>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 align-top text-xs" style={{ color: "var(--page-text-secondary)" }}>
                        {row.period_start} → {row.period_end}
                      </td>
                      <td className="px-3 py-3 align-top"><StatusChip status={row.status} /></td>
                      <td className="px-3 py-3 align-top">
                        {row.status === "ready" ? (
                          <div className="flex flex-wrap gap-1.5">
                            {row.formats.map((format) => (
                              <button key={format}
                                onClick={() => accountId && reportsApi.download(accountId, row.id, format)}
                                className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs uppercase transition-colors hover:opacity-80"
                                style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text)" }}>
                                {FORMAT_ICON[format]}
                                {format}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>—</span>
                        )}
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

function StatusChip({ status }: { status: ReportRow["status"] }) {
  if (status === "ready") {
    return (
      <span className="flex items-center gap-1 text-xs" style={{ color: "#10b981" }}>
        <CheckCircle2 className="h-3.5 w-3.5" /> ready
      </span>
    );
  }
  if (status === "failed") return <Badge variant="danger">failed</Badge>;
  return (
    <span className="flex items-center gap-1 text-xs" style={{ color: "var(--page-text-secondary)" }}>
      {status === "generating" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clock className="h-3.5 w-3.5" />}
      {status}
    </span>
  );
}
