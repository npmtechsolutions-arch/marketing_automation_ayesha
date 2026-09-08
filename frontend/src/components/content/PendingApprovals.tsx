import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, ClipboardCheck, Loader2 } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/Badge";
import api, { getAccountId } from "@/lib/api";
import { AWAITING_REVIEW, statusMeta } from "@/lib/review";

interface PendingPost {
  id: string;
  title: string | null;
  content: string;
  status: string;
  created_at: string;
}

/**
 * What is waiting on somebody.
 *
 * Queried per status rather than filtered client-side, so a workspace with a
 * thousand posts does not pull them all to show three. A CLIENT sees only
 * `client_review` here for the same reason they see it in the list — the
 * server narrows the query, not the display.
 */
export function PendingApprovals() {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<PendingPost[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const accountId = await getAccountId();
      if (!accountId) return;
      const results = await Promise.all(
        AWAITING_REVIEW.map(async (status) => {
          try {
            const res: any = await api.get(
              `/accounts/${accountId}/posts/?status=${status}&per_page=5`
            );
            return ((res.data ?? res).items ?? []) as PendingPost[];
          } catch {
            // A status the caller cannot see returns nothing rather than
            // failing the whole widget.
            return [];
          }
        })
      );
      const merged = results.flat();
      const seen = new Set<string>();
      setPosts(
        merged.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true))).slice(0, 6)
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <GlassCard className="p-5 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: "var(--page-text-muted)" }} />
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <ClipboardCheck className="w-4 h-4 text-purple-400" />
        <h3 className="text-sm font-semibold" style={{ color: "var(--page-heading)" }}>
          Awaiting approval
        </h3>
        {posts.length > 0 && <Badge variant="warning">{posts.length}</Badge>}
      </div>

      {posts.length === 0 ? (
        <div className="text-center py-6">
          <CheckCircle2 className="w-6 h-6 mx-auto mb-2 opacity-40 text-emerald-400" />
          <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
            Nothing is waiting on a review.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {posts.map((post) => {
            const meta = statusMeta(post.status);
            return (
              <li key={post.id}>
                <button
                  onClick={() => navigate(`/calendar?post=${post.id}`)}
                  className="w-full text-left rounded-xl p-2.5 hover:opacity-80 transition-opacity"
                  style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs truncate" style={{ color: "var(--page-text)" }}>
                      {post.title || post.content.slice(0, 48) || "Untitled post"}
                    </span>
                    <Badge variant={meta.variant}>{meta.label}</Badge>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </GlassCard>
  );
}

export default PendingApprovals;
