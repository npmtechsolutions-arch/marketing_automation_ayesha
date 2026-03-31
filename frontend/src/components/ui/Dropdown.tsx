import { type ReactNode } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface DropdownItem {
  label: string;
  icon?: ReactNode;
  onClick?: () => void;
  danger?: boolean;
  separator?: boolean;
}

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
}

export function Dropdown({
  trigger,
  items,
  align = "end",
  side = "bottom",
}: DropdownProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>

      <AnimatePresence>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align={align}
            side={side}
            sideOffset={8}
            asChild
          >
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.96 }}
              transition={{ duration: 0.15 }}
              className="z-50 min-w-[180px] rounded-xl bg-slate-900/95 backdrop-blur-xl border border-white/10 p-1.5 shadow-xl shadow-black/40"
            >
              {items.map((item, i) => {
                if (item.separator) {
                  return (
                    <DropdownMenu.Separator
                      key={i}
                      className="my-1.5 h-px bg-white/10"
                    />
                  );
                }

                return (
                  <DropdownMenu.Item
                    key={i}
                    onClick={item.onClick}
                    className={cn(
                      "flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg outline-none cursor-pointer transition-colors",
                      item.danger
                        ? "text-red-400 hover:bg-red-500/10 focus:bg-red-500/10"
                        : "text-gray-300 hover:bg-white/10 hover:text-white focus:bg-white/10 focus:text-white"
                    )}
                  >
                    {item.icon && (
                      <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>
                    )}
                    {item.label}
                  </DropdownMenu.Item>
                );
              })}
            </motion.div>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </AnimatePresence>
    </DropdownMenu.Root>
  );
}
