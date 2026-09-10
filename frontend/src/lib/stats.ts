/**
 * How a measurement is turned into something a person reads.
 *
 * Both rules here were defects found in Walk B, on a workspace that had
 * measured nothing at all:
 *
 * - a stat card showed **"+%"** — a green, upward, positive-looking badge with
 *   no number in it — because the guard was `change !== undefined` and the
 *   dashboard passes `null`. `null >= 0` is true, so "we have nothing to
 *   compare against" rendered as "up";
 * - the same cards showed **0** and **0.00%** where the server had correctly
 *   returned null, because the page coerced with `?? "0"`.
 *
 * Null is not zero and must survive to the pixels, so the decision lives here
 * rather than inline in a component where the next card can get it wrong
 * again.
 */

export interface ChangeBadge {
  /** The number to print, already signed for display. */
  text: string;
  /** Whether to render it as a rise. False means a fall. */
  positive: boolean;
}

/**
 * The badge for a period-over-period change, or null when there isn't one.
 *
 * Returns null for null *and* undefined: "not measured" and "no comparison
 * available" are both absences, and neither is a rise.
 */
export function changeBadge(change: number | null | undefined): ChangeBadge | null {
  if (change === null || change === undefined) return null;
  if (!Number.isFinite(change)) return null;
  const positive = change >= 0;
  return { text: `${positive ? "+" : ""}${change}%`, positive };
}

/**
 * A metric for display: the number, or an em dash where nothing was measured.
 *
 * The em dash is the project's convention everywhere else (CSV writes an empty
 * cell, the report renderers print "—"), and a zero here would be a
 * measurement claiming nobody saw the post.
 */
export function metricText(
  value: number | null | undefined,
  format?: (n: number) => string
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return format ? format(value) : String(value);
}

/**
 * A rate (0-1 from the API) as a percentage, or an em dash.
 *
 * "A rate with no denominator is null, not 0%" — 0% engagement against
 * unmeasured interactions reads as "your content is failing" when the truth is
 * "we cannot measure this".
 */
export function rateText(rate: number | null | undefined, digits = 2): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return "—";
  return `${(rate * 100).toFixed(digits)}%`;
}
