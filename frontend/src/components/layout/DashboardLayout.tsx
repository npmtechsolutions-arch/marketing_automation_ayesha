import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import GradientMesh from "@/components/shared/GradientMesh";
import FeedbackWidget from "@/components/shared/FeedbackWidget";

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="relative flex h-screen overflow-hidden bg-slate-950">
      {/* Animated background */}
      <GradientMesh />

      {/* Sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="relative flex flex-1 flex-col overflow-hidden">
        <TopBar />

        <main className="flex-1 overflow-y-auto px-4 py-6 lg:px-8">
          {children}
        </main>
      </div>

      <FeedbackWidget />
    </div>
  );
}
