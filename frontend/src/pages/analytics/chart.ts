/** Shared recharts theming, so the four tabs look like one page. */

export const SERIES = {
  purple: "#8b5cf6",
  blue: "#3b82f6",
  emerald: "#10b981",
  amber: "#f59e0b",
  rose: "#f43f5e",
  cyan: "#06b6d4",
  muted: "#94a3b8",
};

/** Colour per platform, matched to the icons elsewhere in the app. */
export const PLATFORM_COLORS: Record<string, string> = {
  instagram: "#e1306c",
  facebook: "#1877f2",
  twitter: "#1da1f2",
  linkedin: "#0a66c2",
  youtube: "#ff0000",
  tiktok: "#00f2ea",
};

export function platformColor(slug: string, index = 0): string {
  return PLATFORM_COLORS[slug] ?? Object.values(SERIES)[index % Object.values(SERIES).length];
}

/** Axis styling that reads in both themes -- CSS variables, not fixed hexes. */
export const chartAxis = {
  stroke: "var(--page-text-muted)",
  tick: { fontSize: 11, fill: "var(--page-text-muted)" },
  tickLine: false,
  axisLine: false,
} as const;

export const chartTooltip = {
  contentStyle: {
    backgroundColor: "var(--surface-bg)",
    border: "1px solid var(--surface-border)",
    borderRadius: 12,
    fontSize: 12,
    color: "var(--page-text)",
  },
  labelStyle: { color: "var(--page-heading)" },
  // Recharts renders a null datum as nothing; make the absence explicit rather
  // than letting the row silently vanish from the tooltip.
  formatter: (value: unknown, name: unknown) => [
    value === null || value === undefined ? "—" : (value as number).toLocaleString(),
    name as string,
  ],
} as const;
