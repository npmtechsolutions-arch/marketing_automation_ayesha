/**
 * CSV import: upload, review, confirm.
 *
 * The review step is the point of the feature. A spreadsheet of fifty posts is
 * exactly where a column is misnamed or a platform misspelt, and finding that
 * out after fifteen rows exist leaves a mess only the user can untangle. So
 * the first upload writes nothing, and the grid shows every row with its own
 * errors before anything is created.
 */
import { useCallback, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { detailFrom } from "@/lib/scheduling";
import {
  analyseCsv,
  confirmCsv,
  downloadTemplate,
  type ImportReport,
  type ImportRow,
} from "@/lib/bulkImport";

type Phase = "choose" | "review" | "done";

export function BulkImportDialog({
  accountId,
  onClose,
  onImported,
}: {
  accountId: string;
  onClose: () => void;
  onImported?: (created: number) => void;
}) {
  const [phase, setPhase] = useState<Phase>("choose");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [showOnlyProblems, setShowOnlyProblems] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyse = useCallback(
    async (chosen: File) => {
      setBusy(true);
      try {
        const result = await analyseCsv(accountId, chosen);
        setFile(chosen);
        setReport(result);
        setPhase("review");
        // Default to the problems when there are any: with fifty rows the
        // three that failed are what the user came to see.
        setShowOnlyProblems(result.rejected > 0);
      } catch (err) {
        showError(detailFrom(err, "That file could not be read."));
      } finally {
        setBusy(false);
      }
    },
    [accountId]
  );

  const confirm = useCallback(async () => {
    if (!file) return;
    setBusy(true);
    try {
      const result = await confirmCsv(accountId, file);
      setReport(result);
      setPhase("done");
      showSuccess(
        `Imported ${result.created} post${result.created === 1 ? "" : "s"}.`
      );
      onImported?.(result.created);
    } catch (err) {
      showError(detailFrom(err, "The import failed."));
    } finally {
      setBusy(false);
    }
  }, [accountId, file, onImported]);

  const visibleRows: ImportRow[] =
    report?.rows.filter((row) => !showOnlyProblems || !row.importable) ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-5xl flex-col rounded-2xl"
        style={{
          backgroundColor: "var(--surface-bg)",
          border: "1px solid var(--surface-border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center gap-3 border-b p-5"
          style={{ borderColor: "var(--surface-border)" }}
        >
          <FileSpreadsheet className="h-5 w-5" style={{ color: "var(--accent-purple)" }} />
          <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
            Import posts from CSV
          </h2>
          <button onClick={onClose} className="ml-auto" style={{ color: "var(--page-text-muted)" }}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {phase === "choose" && (
            <div className="space-y-4">
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                Columns: <code>content</code>, <code>scheduled_at</code>,{" "}
                <code>platforms</code>, <code>media_urls</code>, <code>link</code>.
                Only <code>content</code> is required — a row with no date imports
                as a draft.
              </p>
              <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                Times are read on the workspace's clock, not your computer's, and
                nothing is created until you confirm.
              </p>

              <div
                className="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10"
                style={{ borderColor: "var(--surface-border)" }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const dropped = e.dataTransfer.files?.[0];
                  if (dropped) analyse(dropped);
                }}
              >
                <Upload className="h-8 w-8" style={{ color: "var(--page-text-muted)" }} />
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                  Drop a CSV here, or
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const chosen = e.target.files?.[0];
                    if (chosen) analyse(chosen);
                  }}
                />
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    loading={busy}
                    onClick={() => inputRef.current?.click()}
                  >
                    Choose a file
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Download className="h-3.5 w-3.5" />}
                    onClick={() => downloadTemplate(accountId)}
                  >
                    Template
                  </Button>
                </div>
              </div>
            </div>
          )}

          {phase === "review" && report && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="success">{report.importable} ready</Badge>
                {report.rejected > 0 && (
                  <Badge variant="danger">{report.rejected} with problems</Badge>
                )}
                <span style={{ color: "var(--page-text-muted)" }}>
                  {report.scheduled} scheduled · {report.drafts} draft
                  {report.drafts === 1 ? "" : "s"} · times in {report.timezone}
                </span>
                {report.rejected > 0 && (
                  <button
                    onClick={() => setShowOnlyProblems((v) => !v)}
                    className="ml-auto text-xs"
                    style={{ color: "var(--accent-purple)" }}
                  >
                    {showOnlyProblems ? "Show all rows" : "Show only problems"}
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr style={{ color: "var(--page-text-muted)" }}>
                      <th className="px-2 py-2 text-left font-medium">Row</th>
                      <th className="px-2 py-2 text-left font-medium">Content</th>
                      <th className="px-2 py-2 text-left font-medium">When</th>
                      <th className="px-2 py-2 text-left font-medium">Platforms</th>
                      <th className="px-2 py-2 text-left font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row) => (
                      <tr
                        key={row.row_number}
                        style={{ borderTop: "1px solid var(--surface-border)" }}
                      >
                        <td
                          className="px-2 py-2.5 tabular-nums align-top"
                          style={{ color: "var(--page-text-muted)" }}
                        >
                          {row.row_number}
                        </td>
                        <td className="max-w-[280px] px-2 py-2.5 align-top">
                          <p className="truncate" style={{ color: "var(--page-text)" }}>
                            {row.content || <em>(empty)</em>}
                          </p>
                          {row.errors.map((problem, i) => (
                            <p
                              key={i}
                              className="mt-1 flex items-start gap-1 text-xs"
                              style={{ color: "#f43f5e" }}
                            >
                              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                              <span>
                                <strong>{problem.field}</strong> — {problem.message}
                              </span>
                            </p>
                          ))}
                          {row.warnings.map((problem, i) => (
                            <p
                              key={`w${i}`}
                              className="mt-1 text-xs"
                              style={{ color: "#f59e0b" }}
                            >
                              {problem.field} — {problem.message}
                            </p>
                          ))}
                        </td>
                        <td
                          className="whitespace-nowrap px-2 py-2.5 align-top tabular-nums"
                          style={{ color: "var(--page-text-secondary)" }}
                        >
                          {row.scheduled_at_local ?? "draft"}
                        </td>
                        <td
                          className="px-2 py-2.5 align-top"
                          style={{ color: "var(--page-text-secondary)" }}
                        >
                          {row.platforms.join(", ") || "—"}
                        </td>
                        <td className="px-2 py-2.5 align-top">
                          {row.importable ? (
                            <span
                              className="flex items-center gap-1 text-xs"
                              style={{ color: "#10b981" }}
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" /> ready
                            </span>
                          ) : (
                            <span className="text-xs" style={{ color: "#f43f5e" }}>
                              skipped
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {report.rejected > 0 && report.importable > 0 && (
                <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                  Confirming imports the {report.importable} ready row
                  {report.importable === 1 ? "" : "s"} and skips the rest. Fix the
                  file and upload again to bring in the others.
                </p>
              )}
            </div>
          )}

          {phase === "done" && report && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <CheckCircle2 className="h-10 w-10" style={{ color: "#10b981" }} />
              <p className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
                Imported {report.created} post{report.created === 1 ? "" : "s"}
              </p>
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                {report.scheduled} scheduled, {report.drafts} saved as draft
                {report.rejected > 0 && `, ${report.rejected} skipped`}.
              </p>
            </div>
          )}
        </div>

        <div
          className="flex items-center gap-2 border-t p-4"
          style={{ borderColor: "var(--surface-border)" }}
        >
          {phase === "review" && (
            <>
              <Button
                variant="ghost"
                icon={<ArrowLeft className="h-4 w-4" />}
                onClick={() => {
                  setPhase("choose");
                  setReport(null);
                  setFile(null);
                }}
              >
                Choose another file
              </Button>
              <Button
                variant="primary"
                className="ml-auto"
                loading={busy}
                disabled={report?.importable === 0}
                onClick={confirm}
              >
                {report?.importable
                  ? `Import ${report.importable} post${report.importable === 1 ? "" : "s"}`
                  : "Nothing to import"}
              </Button>
            </>
          )}
          {phase !== "review" && (
            <Button variant="secondary" className={cn("ml-auto")} onClick={onClose}>
              {phase === "done" ? "Done" : "Cancel"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default BulkImportDialog;
