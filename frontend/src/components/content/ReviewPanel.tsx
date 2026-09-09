import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Loader2,
  MessageSquare,
  Send,
  Trash2,
  Undo2,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { showError, showSuccess } from "@/components/ui/Toast";
import {
  addComment,
  deleteComment,
  errorDetail,
  fetchReviewState,
  runReviewAction,
  statusMeta,
  type ReviewState,
} from "@/lib/review";
import { cn } from "@/lib/utils";

const ACTION_META: Record<
  string,
  { label: string; done: string; icon: typeof Send; variant: "primary" | "secondary" | "ghost"; needsComment?: boolean }
> = {
  submit: { label: "Submit for review", done: "Sent for review.", icon: Send, variant: "primary" },
  approve: { label: "Approve", done: "Approved.", icon: CheckCircle2, variant: "primary" },
  request_changes: {
    label: "Request changes",
    done: "Changes requested.",
    icon: XCircle,
    variant: "secondary",
    needsComment: true,
  },
  withdraw: { label: "Withdraw", done: "Withdrawn from review.", icon: Undo2, variant: "ghost" },
};

/**
 * The review panel: where a post stands, who said what, and what you can do.
 *
 * The buttons come from `allowed_actions`, computed server-side against the
 * same transition matrix the endpoints enforce — so the panel cannot offer an
 * action that will 403, and a role that may do nothing simply sees no buttons.
 */
export function ReviewPanel({
  postId,
  onChanged,
}: {
  postId: string;
  onChanged?: () => void;
}) {
  const [state, setState] = useState<ReviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setState(await fetchReviewState(postId));
    } catch (err: any) {
      showError(errorDetail(err, "Could not load the review state."));
    }
    setLoading(false);
  }, [postId]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (action: string) => {
    const meta = ACTION_META[action];
    if (meta?.needsComment && !draft.trim()) {
      showError("Explain what needs to change — a rejection with no reason is one the author has to chase.");
      return;
    }
    setBusy(action);
    try {
      await runReviewAction(postId, action, draft.trim() || undefined);
      setDraft("");
      await load();
      onChanged?.();
      // Each action says what happened, rather than having "done." bolted
      // onto a button label -- which produced "Submit for review done."
      showSuccess(meta?.done ?? "Done.");
    } catch (err: any) {
      showError(errorDetail(err, "That action was refused."));
    }
    setBusy(null);
  };

  const comment = async () => {
    if (!draft.trim()) return;
    setBusy("comment");
    try {
      await addComment(postId, draft.trim());
      setDraft("");
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not post that comment."));
    }
    setBusy(null);
  };

  const removeComment = async (commentId: string) => {
    try {
      await deleteComment(postId, commentId);
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not delete that comment."));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs" style={{ color: "var(--page-text-muted)" }}>
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading review…
      </div>
    );
  }
  if (!state) return null;

  const meta = statusMeta(state.status);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--page-text-secondary)" }}>
            Review
          </h4>
          <Badge variant={meta.variant}>{meta.label}</Badge>
        </div>
        {state.approvals_required && (
          <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>
            {state.client_approval_required
              ? "Internal + client approval required"
              : "Approval required"}
          </span>
        )}
      </div>

      {state.rejection_reason && (
        <div className="rounded-xl p-3 bg-red-500/10 text-red-300 text-xs">
          <span className="font-medium">Changes requested: </span>
          {state.rejection_reason}
        </div>
      )}

      {/* Timeline. Transitions leave a comment behind, so this reads as one
          conversation rather than a status field plus a separate chat. */}
      {state.comments.length > 0 && (
        <ul className="space-y-2.5">
          {state.comments.map((entry) => (
            <li key={entry.id} className="flex gap-2.5">
              <div
                className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center text-[10px] font-medium"
                style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text)" }}
              >
                {(entry.author?.full_name ?? "?").slice(0, 1).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium" style={{ color: "var(--page-text)" }}>
                    {entry.author?.full_name ?? "Unknown"}
                  </span>
                  <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>
                    {new Date(entry.created_at).toLocaleString()}
                    {entry.edited_at ? " (edited)" : ""}
                  </span>
                  <button
                    onClick={() => removeComment(entry.id)}
                    className="ml-auto opacity-0 hover:opacity-100 focus:opacity-100 transition-opacity"
                  >
                    <Trash2 className="w-3 h-3 text-red-400" />
                  </button>
                </div>
                <p className="text-xs mt-0.5 whitespace-pre-wrap break-words" style={{ color: "var(--page-text-secondary)" }}>
                  {entry.body}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {state.allowed_actions.length > 0 || state.comments.length >= 0 ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            placeholder="Add a comment, or explain what needs to change…"
            className="w-full rounded-xl px-3 py-2 text-xs outline-none resize-y"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              icon={<MessageSquare className="w-3.5 h-3.5" />}
              loading={busy === "comment"}
              onClick={comment}
            >
              Comment
            </Button>
            {state.allowed_actions.map((action) => {
              const config = ACTION_META[action];
              if (!config) return null;
              const Icon = config.icon;
              return (
                <Button
                  key={action}
                  variant={config.variant}
                  icon={<Icon className="w-3.5 h-3.5" />}
                  loading={busy === action}
                  onClick={() => act(action)}
                >
                  {config.label}
                </Button>
              );
            })}
          </div>
        </div>
      ) : null}

      {state.due_at && (
        <p className="text-[11px] flex items-center gap-1.5" style={{ color: "var(--page-text-muted)" }}>
          <Clock className="w-3 h-3" />
          Due {new Date(state.due_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

export default ReviewPanel;
