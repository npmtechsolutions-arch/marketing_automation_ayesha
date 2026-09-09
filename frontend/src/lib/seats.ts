/** How many team seats a workspace has used, said honestly.
 *
 *  The team page used to hardcode `const planLimit = 10` and the literal string
 *  `"Growth Plan"`. A brand-new Free workspace was told **"1 of 10 team members
 *  used · Growth Plan"** and then refused on the very next click with "You have
 *  reached your Free plan's limit for team members (1)". Two contradicting
 *  numbers on one screen, one of them a placeholder someone pasted in from the
 *  middle tier.
 *
 *  The real values come from `GET /accounts/{id}/settings/`, which resolves
 *  them from `plan_features` -- the same table the enforcement reads, so the
 *  meter and the refusal cannot disagree.
 */

/** `null` limit means unlimited, which is how the API expresses an enterprise
 *  plan. It is not "no seats", and it is not a number. */
export interface SeatUsage {
  used: number;
  limit: number | null;
  planName: string | null;
}

export interface SeatSummary {
  /** e.g. "1 of 3 team members used", or "2 team members" when unlimited. */
  label: string;
  /** 0-100 for a bar, or null when there is nothing to be a fraction of. */
  percent: number | null;
  /** Whether one more invitation would be refused. */
  atLimit: boolean;
  /** e.g. "Free plan". Null while settings are still loading. */
  planLabel: string | null;
}

/** "free" -> "Free plan". The API sends the plan key, not a display name. */
export function planLabel(tier: string | null | undefined): string | null {
  const key = (tier ?? "").trim();
  if (!key) return null;
  const name = key.charAt(0).toUpperCase() + key.slice(1).toLowerCase();
  return `${name} plan`;
}

export function seatSummary({ used, limit, planName }: SeatUsage): SeatSummary {
  const label =
    limit === null
      ? `${used} team member${used === 1 ? "" : "s"}`
      : `${used} of ${limit} team member${limit === 1 ? "" : "s"} used`;

  return {
    label,
    // Unlimited has no denominator, so no bar -- rather than a bar pinned at
    // 0% or 100%, both of which would say something untrue.
    percent: limit === null || limit === 0 ? null : Math.min(100, Math.round((used / limit) * 100)),
    atLimit: limit !== null && used >= limit,
    planLabel: planLabel(planName),
  };
}
