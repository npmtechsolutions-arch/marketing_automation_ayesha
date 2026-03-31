import { useState, useRef, useEffect, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

interface SelectProps {
  options: SelectOption[];
  value?: string;
  onChange?: (value: string) => void;
  label?: string;
  error?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function Select({
  options,
  value,
  onChange,
  label,
  error,
  placeholder = "Select an option",
  disabled = false,
  className,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className={cn("relative w-full", className)} ref={ref}>
      {label && (
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "#374151" }}>
          {label}
        </label>
      )}

      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        style={{
          backgroundColor: "#ffffff",
          color: selected ? "#1f2937" : "#9ca3af",
          borderColor: error ? "#f87171" : open ? "#7c3aed" : "#d1d5db",
          boxShadow: open ? "0 0 0 3px rgba(124,58,237,0.08)" : "none",
        }}
        className={cn(
          "flex w-full items-center justify-between rounded-xl border px-4 py-2.5 text-sm outline-none transition-all duration-200",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <span>
          {selected ? (
            <span className="flex items-center gap-2" style={{ color: "#1f2937" }}>
              {selected.icon}
              {selected.label}
            </span>
          ) : (
            placeholder
          )}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")}
          style={{ color: "#9ca3af" }}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              boxShadow: "0 12px 40px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
            }}
            className="absolute z-50 mt-1.5 max-h-60 w-full overflow-y-auto rounded-xl p-1"
          >
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange?.(option.value);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-gray-50"
                style={{
                  color: option.value === value ? "#7c3aed" : "#374151",
                  backgroundColor: option.value === value ? "#f5f3ff" : undefined,
                }}
              >
                <span className="flex items-center gap-2">
                  {option.icon}
                  {option.label}
                </span>
                {option.value === value && <Check className="h-4 w-4" style={{ color: "#7c3aed" }} />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p className="mt-1.5 pl-1 text-xs" style={{ color: "#f87171" }}>{error}</p>
      )}
    </div>
  );
}
