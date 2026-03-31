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

const variantStyles: Record<Exclude<Variant, "platform">, { bg: string; text: string; dot: string }> = {
  default: {
    bg: "#f3f4f6",
    text: "#4b5563",
    dot: "#9ca3af",
  },
  success: {
    bg: "#ecfdf5",
    text: "#059669",
    dot: "#10b981",
  },
  warning: {
    bg: "#fffbeb",
    text: "#d97706",
    dot: "#f59e0b",
  },
  danger: {
    bg: "#fef2f2",
    text: "#dc2626",
    dot: "#ef4444",
  },
  info: {
    bg: "#eff6ff",
    text: "#2563eb",
    dot: "#3b82f6",
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
      style={{ backgroundColor: styles.bg, color: styles.text }}
    >
      {dot && <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: styles.dot }} />}
      {children}
    </span>
  );
}
