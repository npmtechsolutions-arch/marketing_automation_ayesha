/**
 * CSV post import.
 *
 * Two phases, and the client must respect the distinction: uploading without
 * `confirm` validates and writes nothing, so the preview the user approves is
 * a genuine dry run. Confirming re-sends the same file — no server-side
 * session is held between the two, which means a stale preview cannot be
 * confirmed against a file that has since changed.
 */
import api from "@/lib/api";

export interface RowProblem {
  field: string;
  message: string;
}

export interface ImportRow {
  row_number: number;
  content: string;
  scheduled_at_local: string | null;
  platforms: string[];
  media_urls: string[];
  link: string | null;
  errors: RowProblem[];
  warnings: RowProblem[];
  importable: boolean;
  run_at: string | null;
  target_count: number;
}

export interface ImportReport {
  rows: ImportRow[];
  total: number;
  importable: number;
  rejected: number;
  scheduled: number;
  drafts: number;
  /** The workspace's clock, which every scheduled_at in the file is read on. */
  timezone: string;
  confirmed: boolean;
  created: number;
  post_ids?: string[];
}

const base = (accountId: string) => `/accounts/${accountId}/posts/bulk-import`;

export async function analyseCsv(
  accountId: string,
  file: File
): Promise<ImportReport> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<ImportReport>(`${base(accountId)}?confirm=false`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function confirmCsv(
  accountId: string,
  file: File
): Promise<ImportReport> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<ImportReport>(`${base(accountId)}?confirm=true`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

/**
 * Download the template.
 *
 * Fetched through axios rather than linked, because the access token lives in
 * memory: a bare `<a href>` to the API would arrive unauthenticated.
 */
export async function downloadTemplate(accountId: string): Promise<void> {
  const res = await api.get(`${base(accountId)}/template`, { responseType: "blob" });
  const url = URL.createObjectURL(
    new Blob([res.data], { type: "text/csv;charset=utf-8" })
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "post-import-template.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
