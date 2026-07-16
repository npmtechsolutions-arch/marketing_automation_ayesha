import { type ReactNode } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

interface GlassCardProps
  extends Omit<HTMLMotionProps<"div">, "children" | "className" | "onClick"> {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: boolean;
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
}

const paddingMap = {
  sm: "p-3",
  md: "p-5",
  lg: "p-7",
};

export function GlassCard({
  children,
  className,
  hover = false,
  glow = false,
  padding = "md",
  onClick,
  ...rest
}: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      whileHover={hover ? { y: -3, transition: { duration: 0.2 } } : undefined}
      onClick={onClick}
      style={{
        backgroundColor: "var(--surface-bg)",
        border: glow ? "1px solid var(--surface-border-hover)" : "1px solid var(--surface-border)",
        boxShadow: glow ? "var(--surface-shadow-hover)" : "var(--surface-shadow)",
        borderRadius: "16px",
      }}
      className={cn(
        paddingMap[padding],
        hover && "cursor-pointer transition-shadow duration-300 hover:shadow-md",
        onClick && "cursor-pointer",
        className
      )}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
