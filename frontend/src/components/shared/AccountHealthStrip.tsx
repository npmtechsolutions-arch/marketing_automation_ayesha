import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The warning strip: connections that will stop publishing.
 *
 * Shown on the dashboard because a broken connection is not discovered until a
 * post fails on it, and by then the slot is gone. Renders nothing when
 * everything is healthy — a permanent banner is one people stop seeing.
 */
export function AccountHealthStrip({
  expiring,
  failed,
}: {
  expiring: number;
  failed: number;
}) {
  const navigate = useNavigate();
  if (!expiring && !failed) return null;

  const critical = failed > 0;
  const parts: string[] = [];
  if (failed) parts.push(`${failed} disconnected`);
  if (expiring) parts.push(`${expiring} expiring`);

  return (
    <button
      onClick={() => navigate("/social-accounts")}
      className={cn(
        "w-full flex items-center gap-3 rounded-2xl px-4 py-3 text-left transition-opacity hover:opacity-90",
        critical
          ? "bg-red-500/10 border border-red-500/25"
          : "bg-amber-500/10 border border-amber-500/25"
      )}
    >
      {critical ? (
        <XCircle className="w-5 h-5 text-red-400 shrink-0" />
      ) : (
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm font-medium", critical ? "text-red-200" : "text-amber-200")}>
          {parts.join(", ")} social {failed + expiring === 1 ? "connection" : "connections"}
        </p>
        <p className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
          {critical
            ? "Scheduled posts to these accounts will fail until they are reconnected."
            : "Reconnect them to avoid an interruption."}
        </p>
      </div>
      <ArrowRight className={cn("w-4 h-4 shrink-0", critical ? "text-red-400" : "text-amber-400")} />
    </button>
  );
}

export default AccountHealthStrip;
