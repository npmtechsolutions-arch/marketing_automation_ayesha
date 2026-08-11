# Dashboard — page overrides

Extends `../MASTER.md`. Direction: refined violet (Linear/Stripe-grade), foundation tokens in `src/index.css`.

## Layout
- Root: `space-y-6 pb-8` inside `DashboardLayout`.
- Header: greeting (name in violet gradient `linear-gradient(120deg,#6d5ef6,#8b5cf6)`) + date; action buttons right-aligned, wrap on mobile.
- Stat row: `grid sm:grid-cols-2 lg:grid-cols-4`, uses shared `StatCard` (tokenized, tabular-nums).
- Body: `grid lg:grid-cols-3` → Performance chart (`lg:col-span-2`) + Notifications; then full-width Top Posts.

## Section headers
Icon chip pattern: `h-9 w-9 rounded-lg`, tinted bg/border of the section's accent, icon `h-5 w-5`.
- Performance → violet `rgba(109,94,246,*)`
- Notifications → amber `#f59e0b`
- Top Posts → emerald `#10b981`

## Charts (recharts)
Theme-aware palette derived from `useUIStore().theme`:
- Series: reach `#6d5ef6` (violet), engagement `#14b8a6` (teal) — colorblind-friendly pair.
- Grid: `rgba(255,255,255,0.06)` dark / `rgba(15,23,42,0.06)` light; `vertical={false}`.
- Axis tick: `#94a3b8` dark / `#64748b` light; `tickLine/axisLine={false}`.
- Custom `ChartTooltip` (theme bg/border/text, blur, colored dots, tabular-nums).
- Always render a legend row; area `strokeWidth 2.5`, gradient fill fading to 0; `role="img"` + `aria-label` summary.

## Rules applied
- No hardcoded `text-white` / `bg-white/5` — everything reads `--page-heading` / `--page-text` / `--surface-*` / `--sidebar-hover-bg` so light + dark are both correct.
- Inset rows: `bg var(--sidebar-hover-bg)` + `1px solid var(--surface-border)`.
- All numeric values use `tabular-nums`.
- Loading uses shared `Skeleton` (token shimmer), not `bg-white/5`.
- Empty states: icon (30% opacity) + message + optional CTA.
