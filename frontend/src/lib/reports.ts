/**
 * Reports.
 *
 * Creating one returns 202 and a PENDING row — the files do not exist yet, so
 * the page polls rather than expecting them. Download hands back a short-lived
 * presigned URL rather than the bytes: the file is already in object storage
 * and proxying a megabyte of PDF through the API buys nothing.
 */
import api from "@/lib/api";

export type ReportType = "weekly" | "monthly" | "quarterly" | "custom";
export type ReportStatus = "pending" | "generating" | "ready" | "failed";
export type ReportFormat = "pdf" | "csv" | "xlsx";

export interface ReportRow {
  id: string;
  title: string | null;
  type: ReportType;
  status: ReportStatus;
  period_start: string;
  period_end: string;
  /** Only the formats that actually rendered. A missing "pdf" means the host
   *  could not produce one, not that the report is broken. */
  formats: ReportFormat[];
  executive_summary: string | null;
  error: string | null;
  generated_at: string | null;
  created_at: string;
}

export interface Branding {
  company_name: string;
  primary_color: string;
  accent_color: string;
  logo_url: string | null;
  footer_note: string | null;
}

export interface BrandingState {
  branding: Branding;
  /** What a report would use today — differs from `branding` when the plan
   *  does not include white-label. */
  effective: Branding;
  white_label: boolean;
  defaults: Branding;
  cadence: "off" | "weekly" | "monthly";
}

const base = (accountId: string) => `/accounts/${accountId}/reports`;

export const reportsApi = {
  list: (accountId: string) =>
    api
      .get<{ reports: ReportRow[]; white_label: boolean }>(`${base(accountId)}/`)
      .then((r) => r.data),

  create: (
    accountId: string,
    body: { type: ReportType; start?: string; end?: string; title?: string }
  ) => api.post<ReportRow>(`${base(accountId)}/`, body).then((r) => r.data),

  branding: (accountId: string) =>
    api.get<BrandingState>(`${base(accountId)}/settings/branding`).then((r) => r.data),

  saveBranding: (accountId: string, body: Partial<Branding>) =>
    api.put(`${base(accountId)}/settings/branding`, body).then((r) => r.data),

  saveCadence: (accountId: string, cadence: "off" | "weekly" | "monthly") =>
    api.put(`${base(accountId)}/settings/cadence`, { cadence }).then((r) => r.data),

  /** Fetch a presigned URL and hand it to the browser. */
  download: async (accountId: string, reportId: string, format: ReportFormat) => {
    const { data } = await api.get<{ url: string }>(
      `${base(accountId)}/${reportId}/download?format=${format}`
    );
    window.open(data.url, "_blank", "noopener,noreferrer");
  },
};

export const REPORT_TYPES: { value: ReportType; label: string; hint: string }[] = [
  { value: "weekly", label: "Weekly", hint: "The last complete Mon–Sun week" },
  { value: "monthly", label: "Monthly", hint: "The last complete calendar month" },
  { value: "quarterly", label: "Quarterly", hint: "The last complete quarter" },
  { value: "custom", label: "Custom", hint: "Any span you choose" },
];
