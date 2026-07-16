import { type ReactNode, type ButtonHTMLAttributes } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg" | "xl";

interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
  iconPosition?: "left" | "right";
  fullWidth?: boolean;
  className?: string;
}

const sizeStyles: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs gap-1.5 rounded-lg",
  md: "px-4 py-2 text-sm gap-2 rounded-xl",
  lg: "px-6 py-2.5 text-base gap-2.5 rounded-xl",
  xl: "px-8 py-3.5 text-lg gap-3 rounded-2xl",
};

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  icon,
  iconPosition = "left",
  fullWidth = false,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  // Inline styles per variant to avoid CSS override conflicts
  const variantInline: Record<Variant, React.CSSProperties> = {
    primary: {
      backgroundColor: "#7c3aed",
      color: "#ffffff",
      boxShadow: "0 2px 8px rgba(124,58,237,0.2)",
    },
    secondary: {
      backgroundColor: "transparent",
      color: "var(--accent-purple)",
      border: "1.5px solid var(--accent-purple)",
    },
    ghost: {
      backgroundColor: "transparent",
      color: "var(--page-text-secondary)",
    },
    danger: {
      backgroundColor: "#e11d48",
      color: "#ffffff",
      boxShadow: "0 2px 8px rgba(225,29,72,0.2)",
    },
    success: {
      backgroundColor: "#059669",
      color: "#ffffff",
      boxShadow: "0 2px 8px rgba(5,150,105,0.2)",
    },
  };

  return (
    <motion.button
      type={type}
      disabled={isDisabled}
      whileHover={isDisabled ? undefined : { scale: 1.02, y: -1 }}
      whileTap={isDisabled ? undefined : { scale: 0.98 }}
      transition={{ duration: 0.15 }}
      style={variantInline[variant]}
      className={cn(
        "relative inline-flex items-center justify-center font-semibold transition-all duration-200",
        sizeStyles[size],
        variant === "secondary" && "hover:bg-violet-50",
        variant === "ghost" && "hover:bg-gray-100",
        fullWidth && "w-full",
        isDisabled && "opacity-50 cursor-not-allowed pointer-events-none",
        className
      )}
      {...(rest as any)}
    >
      {loading ? (
        <>
          <Spinner />
          <span>Loading...</span>
        </>
      ) : (
        <>
          {icon && iconPosition === "left" && icon}
          {children}
          {icon && iconPosition === "right" && icon}
        </>
      )}
    </motion.button>
  );
}
