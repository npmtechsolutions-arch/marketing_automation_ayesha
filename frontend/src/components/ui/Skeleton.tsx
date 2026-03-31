import { cn } from "@/lib/utils";

interface SkeletonProps {
  variant?: "text" | "circle" | "card" | "rect";
  width?: string;
  height?: string;
  count?: number;
  className?: string;
}

const variantDefaults: Record<string, { w: string; h: string; rounded: string }> = {
  text: { w: "100%", h: "14px", rounded: "rounded-md" },
  circle: { w: "40px", h: "40px", rounded: "rounded-full" },
  card: { w: "100%", h: "120px", rounded: "rounded-2xl" },
  rect: { w: "100%", h: "40px", rounded: "rounded-xl" },
};

export function Skeleton({
  variant = "text",
  width,
  height,
  count = 1,
  className,
}: SkeletonProps) {
  const defaults = variantDefaults[variant];

  const items = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      className={cn(
        "animate-pulse bg-white/[0.06]",
        defaults.rounded,
        className
      )}
      style={{
        width: width ?? defaults.w,
        height: height ?? defaults.h,
      }}
    />
  ));

  if (count === 1) return items[0];

  return <div className="flex flex-col gap-2.5">{items}</div>;
}
