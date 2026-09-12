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
      {/* A white segmented control on the lavender canvas -- the active tab
          is a raised white pill rather than a tinted block, so the accent is
          spent on the label and the ring, not on a filled background. */}
      <TabsPrimitive.List
        className="flex items-center gap-1 p-1.5 rounded-full mb-6"
        style={{
          backgroundColor: "var(--surface-bg)",
          border: "1px solid var(--surface-border)",
          boxShadow: "var(--shadow-control)",
        }}
      >
        {tabs.map((tab) => (
          <TabsPrimitive.Trigger
            key={tab.value}
            value={tab.value}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-full transition-all duration-200 outline-none flex-1 justify-center cursor-pointer",
              "text-[color:var(--page-text-secondary)] hover:text-[color:var(--page-text)]",
              "focus-visible:ring-2 focus-visible:ring-[color:var(--accent-ring)]",
              // Active nav is one of the four places the accent is allowed.
              "data-[state=active]:bg-[color:var(--accent-soft)]",
              "data-[state=active]:text-[color:var(--accent)]",
              "data-[state=active]:shadow-none"
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
