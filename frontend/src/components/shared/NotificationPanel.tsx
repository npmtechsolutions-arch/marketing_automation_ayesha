import { motion } from "framer-motion";
import {
  CheckCircle,
  Info,
  AlertTriangle,
  Sparkles,
  Bell,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Notification {
  id: string;
  type: "success" | "info" | "alert" | "ai";
  title: string;
  message: string;
  time: string;
  read: boolean;
}

const typeConfig = {
  success: {
    icon: CheckCircle,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
  },
  info: {
    icon: Info,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
  },
  alert: {
    icon: AlertTriangle,
    color: "text-red-400",
    bg: "bg-red-500/10",
  },
  ai: {
    icon: Sparkles,
    color: "text-purple-400",
    bg: "bg-purple-500/10",
  },
};

// Sample notifications for display
const sampleNotifications: Notification[] = [
  {
    id: "1",
    type: "success",
    title: "Post Published",
    message: "Your Instagram post 'Summer Collection' was published successfully.",
    time: "2h ago",
    read: false,
  },
  {
    id: "2",
    type: "ai",
    title: "AI Suggestion",
    message: "New content ideas generated for your upcoming campaign.",
    time: "4h ago",
    read: false,
  },
  {
    id: "3",
    type: "info",
    title: "Analytics Update",
    message: "Your weekly analytics report is ready to view.",
    time: "6h ago",
    read: true,
  },
  {
    id: "4",
    type: "alert",
    title: "Connection Issue",
    message: "Your Twitter/X connection needs to be re-authenticated.",
    time: "1d ago",
    read: true,
  },
];

export default function NotificationPanel() {
  const notifications = sampleNotifications;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl sm:w-96"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <h3 className="text-sm font-semibold text-white">Notifications</h3>
        <button className="text-xs text-purple-400 transition-colors hover:text-purple-300">
          Mark all read
        </button>
      </div>

      {/* Notification list */}
      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/5">
              <Bell className="h-6 w-6 text-slate-600" />
            </div>
            <p className="text-sm text-slate-500">No notifications yet</p>
          </div>
        ) : (
          notifications.map((notification) => {
            const config = typeConfig[notification.type];
            const Icon = config.icon;

            return (
              <button
                key={notification.id}
                className={cn(
                  "flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5",
                  !notification.read && "bg-white/[0.02]"
                )}
              >
                <div
                  className={cn(
                    "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                    config.bg
                  )}
                >
                  <Icon className={cn("h-4 w-4", config.color)} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-white">
                      {notification.title}
                    </p>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <span className="whitespace-nowrap text-[11px] text-slate-500">
                        {notification.time}
                      </span>
                      {!notification.read && (
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                      )}
                    </div>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-slate-400">
                    {notification.message}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="border-t border-white/5 px-4 py-2.5">
          <button className="w-full text-center text-xs font-medium text-purple-400 transition-colors hover:text-purple-300">
            View All Notifications
          </button>
        </div>
      )}
    </motion.div>
  );
}
