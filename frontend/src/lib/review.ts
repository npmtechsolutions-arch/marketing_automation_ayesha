import api, { getAccountId } from "@/lib/api";

/** Mirrors PostStatus in app/models/post.py */
export type ReviewStatus =
  | "draft"
  | "preview"
  | "pending_approval"
  | "in_review"
  | "changes_requested"
  | "client_review"
  | "approved"
  | "scheduled"
  | "publishing"
  | "published"
  | "partially_published"
  | "failed";

export type BadgeVariant = "success" | "info" | "default" | "danger" | "warning";

/**
 * One label and colour per status, used by the calendar, the list and the
 * review panel. Defined once because three views disagreeing about what
 * "in_review" looks like is how a workflow stops being legible.
 */
export const STATUS_META: Record<
  ReviewStatus,
  { label: string; variant: BadgeVariant }
> = {
  draft: { label: "Draft", variant: "default" },
  preview: { label: "Preview", variant: "default" },
  // Legacy: superseded by in_review, kept because old rows may still carry it.
  pending_approval: { label: "In review", variant: "warning" },
  in_review: { label: "In review", variant: "warning" },
  changes_requested: { label: "Changes requested", variant: "danger" },
  client_review: { label: "With client", variant: "info" },
  approved: { label: "Approved", variant: "success" },
  scheduled: { label: "Scheduled", variant: "info" },
  publishing: { label: "Publishing", variant: "warning" },
  published: { label: "Published", variant: "success" },
  partially_published: { label: "Partly published", variant: "warning" },
  failed: { label: "Failed", variant: "danger" },
};

export function statusMeta(status: string) {
  return (
    STATUS_META[status as ReviewStatus] ?? { label: status, variant: "default" as const }
  );
}

/** Statuses that are waiting on somebody, for the pending-approvals widget. */
export const AWAITING_REVIEW: ReviewStatus[] = [
  "in_review",
  "pending_approval",
  "client_review",
];

export interface CommentAuthor {
  id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
}

export interface PostComment {
  id: string;
  post_id: string;
  author: CommentAuthor | null;
  body: string;
  mentions: string[];
  parent_id: string | null;
  created_at: string;
  edited_at: string | null;
}

export interface ReviewState {
  post_id: string;
  status: string;
  approvals_required: boolean;
  client_approval_required: boolean;
  /** Computed server-side, so the UI offers exactly what the API accepts. */
  allowed_actions: string[];
  assigned_to: string | null;
  due_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  comments: PostComment[];
}

export const errorDetail = (err: any, fallback: string): string => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
};

async function postBase(postId: string): Promise<string> {
  const accountId = await getAccountId();
  if (!accountId) throw new Error("No workspace selected");
  return `/accounts/${accountId}/posts/${postId}`;
}

export async function fetchReviewState(postId: string): Promise<ReviewState> {
  const res: any = await api.get(`${await postBase(postId)}/review`);
  return res.data ?? res;
}

/** submit | approve | request_changes | withdraw */
export async function runReviewAction(
  postId: string,
  action: string,
  comment?: string
): Promise<void> {
  const path =
    action === "submit"
      ? "submit-for-review"
      : action === "request_changes"
        ? "request-changes"
        : action;
  await api.post(`${await postBase(postId)}/${path}`, { comment: comment ?? null });
}

export async function addComment(
  postId: string,
  body: string,
  parentId?: string | null
): Promise<PostComment> {
  const res: any = await api.post(`${await postBase(postId)}/comments`, {
    body,
    parent_id: parentId ?? null,
  });
  return res.data ?? res;
}

export async function deleteComment(postId: string, commentId: string): Promise<void> {
  await api.delete(`${await postBase(postId)}/comments/${commentId}`);
}

export async function setAssignment(
  postId: string,
  assignedTo: string | null,
  dueAt?: string | null
): Promise<void> {
  const body: Record<string, unknown> = { assigned_to: assignedTo };
  if (dueAt !== undefined) body.due_at = dueAt;
  await api.patch(`${await postBase(postId)}/assignment`, body);
}

/**
 * Render @[uuid] mention tokens as names.
 *
 * The stored form is an id because names are ambiguous and change; this is
 * where it becomes readable. An id that resolves to nobody is left as-is
 * rather than blanked, so a mention of someone since removed does not silently
 * vanish from the thread.
 */
export function renderMentions(
  body: string,
  names: Record<string, string>
): string {
  return body.replace(/@\[([0-9a-fA-F-]{36})\]/g, (whole, id) =>
    names[id] ? `@${names[id]}` : whole
  );
}
