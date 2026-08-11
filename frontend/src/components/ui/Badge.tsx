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

// Translucent tinted chips so badges read correctly on both light and dark
// surfaces (the tint composites over whatever surface it sits on) and keep a
// consistent, premium feel across the app.
const variantStyles: Record<Exclude<Variant, "platform">, { bg: string; text: string; dot: string; border: string }> = {
  default: {
    bg: "rgba(100,116,139,0.14)",
    text: "var(--page-text-secondary)",
    dot: "#94a3b8",
    border: "rgba(100,116,139,0.22)",
  },
  success: {
    bg: "rgba(16,185,129,0.14)",
    text: "#10b981",
    dot: "#10b981",
    border: "rgba(16,185,129,0.28)",
  },
  warning: {
    bg: "rgba(245,158,11,0.15)",
    text: "#f59e0b",
    dot: "#f59e0b",
    border: "rgba(245,158,11,0.30)",
  },
  danger: {
    bg: "rgba(239,68,68,0.14)",
    text: "#f43f5e",
    dot: "#ef4444",
    border: "rgba(239,68,68,0.28)",
  },
  info: {
    bg: "rgba(109,94,246,0.15)",
    text: "#8b7ff9",
    dot: "#6d5ef6",
    border: "rgba(109,94,246,0.30)",
  },
};

const sizeStyles = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
};

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

  const styles = variantStyles[variant as Exclude<Variant, "platform">] ?? variantStyles.default;

  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full font-medium", sizeStyles[size], className)}
      style={{ backgroundColor: styles.bg, color: styles.text, border: `1px solid ${styles.border}` }}
    >
      {dot && <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: styles.dot }} />}
      {children}
    </span>
  );
}
