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
          style={{ color: "#374151" }}
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2"
            style={{ color: "#9ca3af" }}
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
            backgroundColor: "#ffffff",
            color: "#1f2937",
            borderColor: error ? "#f87171" : focused ? "#7c3aed" : "#d1d5db",
            boxShadow: focused
              ? error
                ? "0 0 0 3px rgba(248,113,113,0.1)"
                : "0 0 0 3px rgba(124,58,237,0.08)"
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
        <p className="mt-1.5 pl-1 text-xs" style={{ color: "#f87171" }}>
          {error}
        </p>
      )}
    </div>
  );
}
