/**
 * Unhandled 5xx responses.
 *
 * Only genuine failures land here — a 403 or a validation error is the
 * application working. The list omits tracebacks because fifty of them would
 * be megabytes; clicking a row fetches the one you want.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertOctagon, RefreshCw, Search, X } from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatCard } from "@/components/ui/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { showError } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import {
  adminApi,
  type ApiErrorDetail,
  type ApiErrorPage,
  type ApiErrorSummary,
} from "@/lib/admin";
import { SERIES } from "../analytics/chart";

export default function AdminErrorsPage() {
  const [summary, setSummary] = useState<ApiErrorSummary | null>(null);
  const [page, setPage] = useState<ApiErrorPage | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [exceptionFilter, setExceptionFilter] = useState("");
  const [pathFilter, setPathFilter] = useState("");
  const [selected, setSelected] = useState<ApiErrorDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([
        adminApi.errorSummary(7),
        adminApi.errors({
          page: pageNumber,
          exception_class: exceptionFilter || undefined,
          path: pathFilter || undefined,
        }),
      ]);
      setSummary(s);
      setPage(p);
    } catch {
      showError("Could not load error monitoring.");
    } finally {
      setLoading(false);
    }
  }, [pageNumber, exceptionFilter, pathFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = page ? Math.max(1, Math.ceil(page.total / page.page_size)) : 1;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              API errors
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Unhandled 5xx responses, kept for {page?.retention_days ?? 90} days.
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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Last 7 days"
            value={String(summary?.total ?? 0)}
            icon={<AlertOctagon className="h-5 w-5" />}
            loading={loading && !summary}
          />
          <StatCard
            label="Distinct exceptions"
            value={String(summary?.by_exception.length ?? 0)}
            loading={loading && !summary}
          />
          <StatCard
            label="Affected routes"
            value={String(summary?.by_path.length ?? 0)}
            loading={loading && !summary}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <GlassCard>
            <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              Most frequent — last 7 days
            </h3>
            {(summary?.by_exception.length ?? 0) === 0 ? (
              <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
                Nothing has failed.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {summary?.by_exception.slice(0, 8).map((row) => (
                  <li key={row.exception_class}>
                    <button
                      onClick={() => {
                        setExceptionFilter(row.exception_class);
                        setPageNumber(1);
                      }}
                      className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:opacity-80"
                      style={{ color: "var(--page-text)" }}
                    >
                      <span className="truncate font-mono text-xs">{row.exception_class}</span>
                      <span
                        className="ml-auto rounded-md px-2 py-0.5 text-xs tabular-nums"
                        style={{ backgroundColor: "var(--sidebar-hover-bg)", color: SERIES.rose }}
                      >
                        {row.count}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>

          <GlassCard>
            <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              Worst routes — last 7 days
            </h3>
            {(summary?.by_path.length ?? 0) === 0 ? (
              <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
                Nothing has failed.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {summary?.by_path.slice(0, 8).map((row) => (
                  <li key={row.path}>
                    <button
                      onClick={() => {
                        setPathFilter(row.path);
                        setPageNumber(1);
                      }}
                      className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:opacity-80"
                      style={{ color: "var(--page-text)" }}
                    >
                      <span className="truncate font-mono text-xs">{row.path}</span>
                      <span
                        className="ml-auto rounded-md px-2 py-0.5 text-xs tabular-nums"
                        style={{ backgroundColor: "var(--sidebar-hover-bg)", color: SERIES.amber }}
                      >
                        {row.count}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>
        </div>

        <GlassCard>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Search className="h-4 w-4" style={{ color: "var(--page-text-muted)" }} />
            <input
              value={exceptionFilter}
              onChange={(e) => {
                setExceptionFilter(e.target.value);
                setPageNumber(1);
              }}
              placeholder="Exception class"
              className="rounded-lg px-2.5 py-1.5 text-xs"
              style={{
                backgroundColor: "var(--input-bg)",
                color: "var(--page-text)",
                border: "1px solid var(--surface-border)",
              }}
            />
            <input
              value={pathFilter}
              onChange={(e) => {
                setPathFilter(e.target.value);
                setPageNumber(1);
              }}
              placeholder="Path prefix, e.g. /api/v1/posts"
              className="min-w-[240px] rounded-lg px-2.5 py-1.5 text-xs"
              style={{
                backgroundColor: "var(--input-bg)",
                color: "var(--page-text)",
                border: "1px solid var(--surface-border)",
              }}
            />
            {(exceptionFilter || pathFilter) && (
              <button
                onClick={() => {
                  setExceptionFilter("");
                  setPathFilter("");
                  setPageNumber(1);
                }}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs"
                style={{ color: "var(--page-text-secondary)" }}
              >
                <X className="h-3 w-3" /> Clear
              </button>
            )}
            <span className="ml-auto text-xs" style={{ color: "var(--page-text-muted)" }}>
              {page?.total ?? 0} matching
            </span>
          </div>

          {loading && !page ? (
            <Skeleton variant="card" height="260px" />
          ) : (page?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={<AlertOctagon className="h-7 w-7" />}
              title="No errors recorded"
              description="Nothing unhandled has reached a 500 in this window."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-sm">
                  <thead>
                    <tr style={{ color: "var(--page-text-muted)" }}>
                      <th className="px-3 py-2 text-left font-medium">When</th>
                      <th className="px-3 py-2 text-left font-medium">Method</th>
                      <th className="px-3 py-2 text-left font-medium">Path</th>
                      <th className="px-3 py-2 text-left font-medium">Exception</th>
                      <th className="px-3 py-2 text-left font-medium">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page?.items.map((row) => (
                      <tr
                        key={row.id}
                        onClick={async () => {
                          try {
                            setSelected(await adminApi.error(row.id));
                          } catch {
                            showError("Could not load that error.");
                          }
                        }}
                        className="cursor-pointer transition-colors hover:opacity-80"
                        style={{ borderTop: "1px solid var(--surface-border)" }}
                      >
                        <td className="whitespace-nowrap px-3 py-2.5" style={{ color: "var(--page-text-muted)" }}>
                          {row.created_at.slice(0, 19).replace("T", " ")}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs" style={{ color: "var(--page-text-secondary)" }}>
                          {row.method}
                        </td>
                        <td className="max-w-[240px] truncate px-3 py-2.5 font-mono text-xs" style={{ color: "var(--page-text)" }}>
                          {row.path}
                        </td>
                        <td className="max-w-[200px] truncate px-3 py-2.5 font-mono text-xs" style={{ color: SERIES.rose }}>
                          {row.exception_class}
                        </td>
                        <td className="max-w-[280px] truncate px-3 py-2.5" style={{ color: "var(--page-text-secondary)" }}>
                          {row.message ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-3 text-xs">
                  <button
                    disabled={pageNumber <= 1}
                    onClick={() => setPageNumber((n) => n - 1)}
                    className="rounded-lg px-3 py-1.5 disabled:opacity-40"
                    style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-secondary)" }}
                  >
                    Previous
                  </button>
                  <span style={{ color: "var(--page-text-muted)" }}>
                    Page {pageNumber} of {totalPages}
                  </span>
                  <button
                    disabled={pageNumber >= totalPages}
                    onClick={() => setPageNumber((n) => n + 1)}
                    className="rounded-lg px-3 py-1.5 disabled:opacity-40"
                    style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-secondary)" }}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </GlassCard>
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
          onClick={() => setSelected(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-2xl p-6"
            style={{
              backgroundColor: "var(--surface-bg)",
              border: "1px solid var(--surface-border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-sm" style={{ color: SERIES.rose }}>
                  {selected.exception_class}
                </p>
                <p className="mt-1 font-mono text-xs" style={{ color: "var(--page-text-secondary)" }}>
                  {selected.method} {selected.path}
                </p>
                <p className="mt-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                  {selected.created_at.slice(0, 19).replace("T", " ")}
                  {selected.user_id && ` · user ${selected.user_id.slice(0, 8)}`}
                </p>
              </div>
              <button onClick={() => setSelected(null)} style={{ color: "var(--page-text-muted)" }}>
                <X className="h-5 w-5" />
              </button>
            </div>
            <pre
              className="overflow-x-auto whitespace-pre-wrap rounded-xl p-4 text-xs leading-relaxed"
              style={{
                backgroundColor: "var(--sidebar-hover-bg)",
                color: "var(--page-text)",
              }}
            >
              {selected.traceback ?? selected.message ?? "No detail recorded."}
            </pre>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
