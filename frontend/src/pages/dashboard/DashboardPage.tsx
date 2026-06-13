import { Plus, CalendarDays, Sparkles } from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/Button";

export default function DashboardPage() {
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl">Welcome back! 👋</h1>
            <p className="mt-1 text-sm text-gray-400">{today}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="primary" icon={<Plus className="w-4 h-4" />}>
              Create Post
            </Button>
            <Button size="sm" variant="secondary" icon={<CalendarDays className="w-4 h-4" />}>
              View Calendar
            </Button>
            <Button size="sm" variant="secondary" icon={<Sparkles className="w-4 h-4" />}>
              Generate Strategy
            </Button>
          </div>
        </div>

        <div className="rounded-2xl p-8 text-center" style={{ background: "var(--surface-bg)", border: "1px solid var(--surface-border)" }}>
          <h2 className="text-lg font-semibold mb-2">Dashboard Data</h2>
          <p className="text-gray-400">Create your first post to see dashboard analytics and insights.</p>
        </div>
      </div>
    </DashboardLayout>
  );
}
