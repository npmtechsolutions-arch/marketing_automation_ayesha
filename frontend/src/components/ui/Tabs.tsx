import { type ReactNode } from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

interface Tab {
  value: string;
  label: string;
  icon?: ReactNode;
  content: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  defaultValue?: string;
  className?: string;
}

export function Tabs({ tabs, defaultValue, className }: TabsProps) {
  return (
    <TabsPrimitive.Root
      defaultValue={defaultValue ?? tabs[0]?.value}
      className={className}
    >
      <TabsPrimitive.List
        className="flex items-center gap-1 p-1 rounded-xl mb-4"
        style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
      >
        {tabs.map((tab) => (
          <TabsPrimitive.Trigger
            key={tab.value}
            value={tab.value}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 outline-none flex-1 justify-center cursor-pointer",
              "text-[color:var(--page-text-secondary)] hover:text-[color:var(--page-text)]",
              "focus-visible:ring-2 focus-visible:ring-purple-400/60",
              "data-[state=active]:bg-[rgba(109,94,246,0.14)]",
              "data-[state=active]:text-[color:var(--page-heading)]",
              "data-[state=active]:shadow-sm data-[state=active]:border data-[state=active]:border-[rgba(109,94,246,0.28)]"
            )}
          >
            {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
            {tab.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>

      {tabs.map((tab) => (
        <TabsPrimitive.Content
          key={tab.value}
          value={tab.value}
          className="outline-none"
        >
          {tab.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
