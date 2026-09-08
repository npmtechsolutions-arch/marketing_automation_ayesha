/** Connection health, mirroring AccountHealth in app/models/platform.py */
export type AccountHealth = "connected" | "expiring" | "failed" | "unknown";

export const HEALTH_META: Record<
  AccountHealth,
  { label: string; variant: "success" | "warning" | "danger" | "default"; blurb: string }
> = {
  connected: {
    label: "Connected",
    variant: "success",
    blurb: "Publishing normally.",
  },
  expiring: {
    label: "Expiring",
    variant: "warning",
    blurb: "This connection will stop working soon. Reconnect to avoid interruption.",
  },
  failed: {
    label: "Disconnected",
    variant: "danger",
    blurb: "Scheduled posts to this account will fail until it is reconnected.",
  },
  // Not yet swept. Deliberately not shown as healthy — a clean bill of health
  // nobody checked is worse than an honest "not checked yet".
  unknown: {
    label: "Not checked",
    variant: "default",
    blurb: "This connection has not been checked yet.",
  },
};

export const healthMeta = (health: string) =>
  HEALTH_META[(health as AccountHealth) ?? "unknown"] ?? HEALTH_META.unknown;

export const needsAttention = (health: string) =>
  health === "expiring" || health === "failed";

/**
 * Where to send someone to re-authorise a connection.
 *
 * `?reconnect=` is what makes the OAuth callback update the existing row
 * instead of creating a second one — without it every reconnect orphans the
 * account's post history.
 */
export function reconnectPath(
  accountId: string,
  platformSlug: string,
  platformId: string,
  socialAccountId: string
): string {
  return (
    `/accounts/${accountId}/${platformSlug}/authorize` +
    `?platform_id=${platformId}&reconnect=${socialAccountId}`
  );
}
