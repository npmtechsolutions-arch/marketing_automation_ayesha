import api, { getAccountId } from "@/lib/api";

/** Mirrors app/schemas/media.py */
export interface MediaItem {
  id: string;
  account_id: string;
  folder_id: string | null;
  uploaded_by: string | null;
  filename: string;
  mime_type: string;
  kind: "image" | "video" | "document";
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  alt_text: string | null;
  tags: string[];
  used_in_posts: number;
  download_url: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface MediaFolder {
  id: string;
  account_id: string;
  name: string;
  parent_id: string | null;
  media_count: number;
  created_at: string;
}

export interface MediaListResult {
  items: MediaItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  storage_used_bytes: number;
  storage_limit_bytes: number | null;
}

export interface MediaQuery {
  search?: string;
  kind?: string;
  folder_id?: string | null;
  root_only?: boolean;
  sort?: "date" | "name" | "size";
  order?: "asc" | "desc";
  page?: number;
  per_page?: number;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${i === 0 ? value : value.toFixed(1)} ${units[i]}`;
}

export function errorDetail(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

async function base(): Promise<string> {
  const accountId = await getAccountId();
  if (!accountId) throw new Error("No workspace selected");
  return `/accounts/${accountId}/media`;
}

export async function listMedia(query: MediaQuery = {}): Promise<MediaListResult> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.kind && query.kind !== "all") params.set("kind", query.kind);
  if (query.folder_id) params.set("folder_id", query.folder_id);
  else if (query.root_only) params.set("root_only", "true");
  params.set("sort", query.sort ?? "date");
  params.set("order", query.order ?? "desc");
  params.set("page", String(query.page ?? 1));
  params.set("per_page", String(query.per_page ?? 60));

  const res: any = await api.get(`${await base()}/?${params}`);
  return res.data ?? res;
}

export async function listFolders(): Promise<MediaFolder[]> {
  const res: any = await api.get(`${await base()}/folders/`);
  return res.data ?? res;
}

export async function createFolder(
  name: string,
  parentId: string | null
): Promise<MediaFolder> {
  const res: any = await api.post(`${await base()}/folders/`, {
    name,
    parent_id: parentId,
  });
  return res.data ?? res;
}

export async function deleteFolder(folderId: string): Promise<void> {
  await api.delete(`${await base()}/folders/${folderId}`);
}

export async function updateMedia(
  mediaId: string,
  changes: { filename?: string; alt_text?: string | null; tags?: string[] }
): Promise<MediaItem> {
  const res: any = await api.patch(`${await base()}/${mediaId}`, changes);
  return res.data ?? res;
}

export async function moveMedia(
  mediaId: string,
  folderId: string | null
): Promise<MediaItem> {
  const res: any = await api.post(`${await base()}/${mediaId}/move`, {
    folder_id: folderId,
  });
  return res.data ?? res;
}

export async function deleteMedia(mediaId: string): Promise<string> {
  const res: any = await api.delete(`${await base()}/${mediaId}`);
  return (res.data ?? res)?.message ?? "Deleted.";
}

/**
 * Presign, PUT to storage, confirm.
 *
 * The PUT goes straight to S3 (or, with no bucket configured, to a signed
 * shim on our own API that behaves the same way). It deliberately does NOT go
 * through the axios instance: that would attach our Authorization header to a
 * request bound for AWS, and S3 rejects a request carrying an unexpected
 * signed header. XMLHttpRequest is used rather than fetch because it reports
 * upload progress, which fetch still cannot.
 */
export async function uploadFile(
  file: File,
  options: { folderId?: string | null; onProgress?: (percent: number) => void } = {}
): Promise<MediaItem> {
  const root = await base();

  const presignRes: any = await api.post(`${root}/presign`, {
    filename: file.name,
    mime_type: file.type,
    size_bytes: file.size,
    folder_id: options.folderId ?? null,
  });
  const presign = presignRes.data ?? presignRes;

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(presign.method, presign.upload_url, true);
    for (const [header, value] of Object.entries(presign.headers ?? {})) {
      xhr.setRequestHeader(header, value as string);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && options.onProgress) {
        options.onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Upload failed (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Upload failed: the network request errored"));
    xhr.send(file);
  });

  const confirmRes: any = await api.post(`${root}/confirm`, {
    key: presign.key,
    filename: file.name,
    mime_type: file.type,
    folder_id: options.folderId ?? null,
  });
  return confirmRes.data ?? confirmRes;
}
