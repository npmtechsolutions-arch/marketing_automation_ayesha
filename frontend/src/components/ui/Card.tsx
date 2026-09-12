/**
 * The surface everything sits on: a white card on the lavender canvas.
 *
 * This replaces `GlassCard`, which stopped being glass some time ago — it had
 * already been reduced to `var(--surface-*)` tokens and a 16px radius, and the
 * name was the only thing left of the original aesthetic. Because it was
 * token-driven, retheming its 420 call sites is a token change rather than a
 * migration: `GlassCard` is re-exported from here with the identical prop
 * signature, so no consumer has to change to get the new skin.
 *
 * Props are unchanged from GlassCard on purpose (`hover`, `glow`, `padding`,
 * `onClick`, plus motion props), because phase 0 is a skin and not a new API.
 */
import { type ReactNode } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

interface CardProps
  extends Omit<HTMLMotionProps<"div">, "children" | "className" | "onClick"> {
  children: ReactNode;
  className?: string;
  /** Lift slightly on hover. Use for cards that are themselves links. */
  hover?: boolean;
  /** Emphasise with the accent border and a deeper shadow. */
  glow?: boolean;
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
}

// Airier than before at every step: md was p-5, lg was p-7. The direction is
// more whitespace, and the card is where most of the product's density lives.
const paddingMap = {
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

export function Card({
  children,
  className,
  hover = false,
  glow = false,
  padding = "md",
  onClick,
  ...rest
}: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      whileHover={hover ? { y: -2, transition: { duration: 0.2 } } : undefined}
      onClick={onClick}
      style={{
        backgroundColor: "var(--surface-bg)",
        // A 1px hairline, and the accent only when the card is deliberately
        // emphasised -- the accent is reserved for primary actions, active
        // nav, links and focus, so a page of cards stays quiet.
        border: `1px solid ${glow ? "var(--accent-soft-border)" : "var(--surface-border)"}`,
        boxShadow: glow ? "var(--surface-shadow-hover)" : "var(--surface-shadow)",
        borderRadius: "var(--surface-radius)",
      }}
      className={cn(
        paddingMap[padding],
        hover &&
          "cursor-pointer transition-shadow duration-300 hover:shadow-[var(--surface-shadow-hover)]",
        onClick && "cursor-pointer",
        className
      )}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/**
 * A small uppercase marker for section headings ("OVERVIEW", "THIS WEEK").
 *
 * New in phase 0 and purely additive: nothing uses it yet, and the page slices
 * adopt it as they are restyled.
 */
export function SectionLabel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-eyebrow font-semibold uppercase",
        className
      )}
      style={{
        backgroundColor: "var(--accent-soft)",
        border: "1px solid var(--accent-soft-border)",
        color: "var(--accent)",
      }}
    >
      {children}
    </span>
  );
}
