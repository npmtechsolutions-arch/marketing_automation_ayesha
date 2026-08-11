import { type ReactNode } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "./Skeleton";

interface StatCardProps {
  label: string;
  value: string;
  change?: number;
  changeLabel?: string;
  icon?: ReactNode;
  loading?: boolean;
}

export function StatCard({
  label,
  value,
  change,
  changeLabel,
  icon,
  loading = false,
}: StatCardProps) {
  if (loading) {
    return (
      <div
        className="rounded-2xl p-5"
        style={{
          backgroundColor: "var(--surface-bg)",
          border: "1px solid var(--surface-border)",
          boxShadow: "var(--surface-shadow)",
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <Skeleton variant="text" width="100px" height="14px" />
          <Skeleton variant="circle" width="40px" height="40px" />
        </div>
        <Skeleton variant="text" width="120px" height="28px" />
        <div className="mt-2">
          <Skeleton variant="text" width="80px" height="14px" />
        </div>
      </div>
    );
  }

  const isPositive = change !== undefined && change >= 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      style={{
        backgroundColor: "var(--surface-bg)",
        border: "1px solid var(--surface-border)",
        boxShadow: "var(--surface-shadow)",
      }}
      className="rounded-2xl p-5 group transition-shadow duration-300 hover:shadow-[var(--surface-shadow-hover)]"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium" style={{ color: "var(--page-text-secondary)" }}>{label}</p>
        {icon && (
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
            style={{
              backgroundColor: "rgba(109,94,246,0.12)",
              border: "1px solid rgba(109,94,246,0.22)",
              color: "var(--accent-purple)",
            }}
          >
            {icon}
          </div>
        )}
      </div>

      <p className="text-2xl font-bold tracking-tight tabular-nums" style={{ color: "var(--page-heading)" }}>{value}</p>

      {change !== undefined && (
        <div className="flex items-center gap-1.5 mt-2">
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-md tabular-nums",
              isPositive
                ? "text-emerald-500 bg-emerald-500/10"
                : "text-red-500 bg-red-500/10"
            )}
          >
            {isPositive ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {isPositive ? "+" : ""}
            {change}%
          </span>
          {changeLabel && (
            <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>{changeLabel}</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
