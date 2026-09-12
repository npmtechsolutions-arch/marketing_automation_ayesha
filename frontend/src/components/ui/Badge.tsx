import { type ReactNode } from "react";
import { cn, getPlatformColor } from "@/lib/utils";

type Variant = "default" | "success" | "warning" | "danger" | "info" | "platform";

interface BadgeProps {
  children: ReactNode;
  variant?: Variant;
  dot?: boolean;
  platform?: string;
  className?: string;
  size?: "sm" | "md";
}

// Five variants, and they stay five distinguishable colours.
//
// This is the one place the single-accent rule does not apply. `src/lib/
// review.ts` maps twelve post statuses onto these five -- published is
// success, failed is danger, in_review and partially_published are warning,
// scheduled and client_review are info -- and that file is a contract the
// calendar, the list and the review panel all read. Collapsing any of these
// into violet would make a failed post look like a scheduled one.
//
// What changed for the redesign is only legibility on the new canvas: the
// tints were translucent, which composited against whatever sat behind them,
// so a badge on a white card and the same badge on the lavender page were
// different colours. These are opaque, from the same 50/600 families as the
// rest of the palette, and each carries its own border and dot.
const variantStyles: Record<Exclude<Variant, "platform">, { bg: string; text: string; dot: string; border: string }> = {
  default: {
    bg: "#f3f4f6",
    text: "#4b5563",
    dot: "#9ca3af",
    border: "#e5e7eb",
  },
  success: {
    bg: "#ecfdf5",
    text: "#047857",
    dot: "#10b981",
    border: "#a7f3d0",
  },
  warning: {
    bg: "#fffbeb",
    text: "#b45309",
    dot: "#f59e0b",
    border: "#fde68a",
  },
  danger: {
    bg: "#fff1f2",
    text: "#be123c",
    dot: "#f43f5e",
    border: "#fecdd3",
  },
  info: {
    bg: "#eff6ff",
    text: "#1d4ed8",
    dot: "#3b82f6",
    border: "#bfdbfe",
  },
};

// Dark mode keeps the translucent treatment: opaque 50-shade chips would glow
// on a near-black surface. Same five hues, same distinctions.
const darkVariantStyles: typeof variantStyles = {
  default: { bg: "rgba(148,163,184,0.16)", text: "#cbd5e1", dot: "#94a3b8", border: "rgba(148,163,184,0.28)" },
  success: { bg: "rgba(16,185,129,0.16)", text: "#6ee7b7", dot: "#10b981", border: "rgba(16,185,129,0.32)" },
  warning: { bg: "rgba(245,158,11,0.16)", text: "#fcd34d", dot: "#f59e0b", border: "rgba(245,158,11,0.32)" },
  danger: { bg: "rgba(244,63,94,0.16)", text: "#fda4af", dot: "#f43f5e", border: "rgba(244,63,94,0.32)" },
  info: { bg: "rgba(59,130,246,0.16)", text: "#93c5fd", dot: "#3b82f6", border: "rgba(59,130,246,0.32)" },
};

const sizeStyles = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
};

/** Whether the app is currently in dark mode, read at render time. */
function isDark(): boolean {
  return (
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark")
  );
}

export function Badge({
  children,
  variant = "default",
  dot = false,
  platform,
  className,
  size = "md",
}: BadgeProps) {
  if (variant === "platform" && platform) {
    const color = getPlatformColor(platform);
    return (
      <span
        className={cn("inline-flex items-center gap-1.5 rounded-full font-medium", sizeStyles[size], className)}
        style={{ backgroundColor: `${color}12`, color: color }}
      >
        {dot && <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />}
        {children}
      </span>
    );
  }

  const palette = isDark() ? darkVariantStyles : variantStyles;
  const styles = palette[variant as Exclude<Variant, "platform">] ?? palette.default;

  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full font-semibold", sizeStyles[size], className)}
      style={{ backgroundColor: styles.bg, color: styles.text, border: `1px solid ${styles.border}` }}
    >
      {dot && <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: styles.dot }} />}
      {children}
    </span>
  );
}
