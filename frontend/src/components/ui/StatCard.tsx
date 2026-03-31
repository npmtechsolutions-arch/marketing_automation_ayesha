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
      <div className="rounded-2xl backdrop-blur-xl bg-white/5 border border-white/10 p-5">
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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="rounded-2xl backdrop-blur-xl bg-white/5 border border-white/10 p-5 group hover:border-white/20 transition-all duration-300"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-400 font-medium">{label}</p>
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center text-purple-400 group-hover:from-purple-600/30 group-hover:to-blue-600/30 transition-colors">
            {icon}
          </div>
        )}
      </div>

      <p className="text-2xl font-bold text-white tracking-tight">{value}</p>

      {change !== undefined && (
        <div className="flex items-center gap-1.5 mt-2">
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-md",
              isPositive
                ? "text-emerald-400 bg-emerald-500/10"
                : "text-red-400 bg-red-500/10"
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
            <span className="text-xs text-gray-500">{changeLabel}</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
