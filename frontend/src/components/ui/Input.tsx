import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "size"> {
  label?: string;
  error?: string;
  icon?: ReactNode;
  className?: string;
}

export function Input({
  label,
  error,
  icon,
  className,
  type = "text",
  value,
  disabled,
  placeholder,
  onFocus,
  onBlur,
  ...rest
}: InputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <div className={cn("relative w-full", className)}>
      {label && (
        <label
          className="mb-1.5 block text-sm font-medium"
          style={{ color: "var(--page-text)" }}
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2"
            style={{ color: "var(--input-placeholder)" }}
          >
            {icon}
          </div>
        )}
        <input
          type={type}
          value={value}
          disabled={disabled}
          placeholder={placeholder || label || ""}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          style={{
            backgroundColor: "var(--input-bg)",
            color: "var(--input-text)",
            borderColor: error ? "var(--accent-red)" : focused ? "var(--input-focus-border)" : "var(--input-border)",
            boxShadow: focused
              ? error
                ? "0 0 0 3px rgba(248,113,113,0.1)"
                : "0 0 0 3px var(--input-focus-ring)"
              : "none",
          }}
          className={cn(
            "w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-all duration-200",
            "placeholder:text-gray-400",
            icon && "pl-11",
            disabled && "cursor-not-allowed opacity-50"
          )}
          {...rest}
        />
      </div>
      {error && (
        <p className="mt-1.5 pl-1 text-xs" style={{ color: "var(--accent-red)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
