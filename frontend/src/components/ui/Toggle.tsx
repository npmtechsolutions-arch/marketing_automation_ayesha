import * as Switch from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

interface ToggleProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
}

export function Toggle({
  checked,
  onCheckedChange,
  label,
  description,
  disabled = false,
}: ToggleProps) {
  return (
    <label
      className={cn(
        "flex items-center justify-between gap-4",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      {(label || description) && (
        <div className="min-w-0 flex-1">
          {label && (
            <p className="text-sm font-medium" style={{ color: "#1f2937" }}>{label}</p>
          )}
          {description && (
            <p className="mt-0.5 text-xs" style={{ color: "#6b7280" }}>{description}</p>
          )}
        </div>
      )}

      <Switch.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className="relative h-6 w-11 flex-shrink-0 rounded-full outline-none transition-colors duration-200"
        style={{ backgroundColor: checked ? "#7c3aed" : "#d1d5db" }}
      >
        <Switch.Thumb
          className={cn(
            "block h-5 w-5 rounded-full bg-white shadow-md transition-transform duration-200 will-change-transform",
            checked ? "translate-x-[22px]" : "translate-x-[2px]"
          )}
        />
      </Switch.Root>
    </label>
  );
}
