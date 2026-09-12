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

// Pills, and roomier than before at every size. A pill reads as an action
// where a 12px-radius rectangle reads as a surface, which matters now that
// cards are the same family of radii.
const sizeStyles: Record<Size, string> = {
  sm: "px-3.5 py-1.5 text-xs gap-1.5 rounded-full",
  md: "px-5 py-2.5 text-sm gap-2 rounded-full",
  lg: "px-6 py-3 text-base gap-2.5 rounded-full",
  xl: "px-8 py-4 text-lg gap-3 rounded-full",
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

  // Inline styles per variant, because the stylesheet still carries a global
  // light-mode override layer that rewrites Tailwind colour classes with
  // !important. Inline styles sit outside it; that layer is dismantled in the
  // app-shell slice, not here.
  //
  // The accent appears on `primary` only. `danger` and `success` keep their own
  // colours: they are semantic, not brand, and a destructive action that looks
  // like every other button is a worse problem than a second hue.
  const variantInline: Record<Variant, React.CSSProperties> = {
    primary: {
      backgroundImage: "var(--accent-gradient)",
      color: "#ffffff",
      boxShadow: "var(--shadow-accent)",
    },
    secondary: {
      backgroundColor: "var(--surface-bg)",
      color: "var(--page-text)",
      border: "1px solid var(--surface-border)",
      boxShadow: "var(--shadow-control)",
    },
    ghost: {
      backgroundColor: "transparent",
      color: "var(--page-text-secondary)",
    },
    danger: {
      backgroundColor: "#e11d48",
      color: "#ffffff",
      boxShadow: "0 1px 2px rgba(225,29,72,0.2), 0 8px 20px -6px rgba(225,29,72,0.35)",
    },
    success: {
      backgroundColor: "#059669",
      color: "#ffffff",
      boxShadow: "0 1px 2px rgba(5,150,105,0.2), 0 8px 20px -6px rgba(5,150,105,0.32)",
    },
  };

  return (
    <motion.button
      type={type}
      disabled={isDisabled}
      whileHover={isDisabled ? undefined : { y: -1 }}
      whileTap={isDisabled ? undefined : { scale: 0.985 }}
      transition={{ duration: 0.15 }}
      style={variantInline[variant]}
      className={cn(
        "relative inline-flex items-center justify-center font-semibold transition-all duration-200",
        // The focus ring is one of the four places the accent is allowed.
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--page-bg)]",
        sizeStyles[size],
        variant === "primary" && "hover:[background-image:var(--accent-gradient-hover)]",
        variant === "secondary" && "hover:bg-[color:var(--accent-soft)]",
        variant === "ghost" && "hover:bg-[color:var(--accent-soft)]",
        fullWidth && "w-full",
        !isDisabled && "cursor-pointer",
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
