import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  Search,
  MoreHorizontal,
  Eye,
  UserCog,
  Ban,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Download,
  Mail,
  Calendar,
  FileText,
  Building2,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { cn, formatDate, formatNumber } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ---------------------------------------------------------------------------
// Mock users
// ---------------------------------------------------------------------------
const mockUsers = [
  { id: 1, name: "Sarah Chen", email: "sarah.chen@techstart.io", avatar: null, plan: "Professional", status: "active" as const, accounts: 3, posts: 482, joined: "2025-06-14" },
  { id: 2, name: "Marcus Williams", email: "marcus@growthlab.co", avatar: null, plan: "Enterprise", status: "active" as const, accounts: 8, posts: 1245, joined: "2025-03-22" },
  { id: 3, name: "Priya Patel", email: "priya@contentforge.com", avatar: null, plan: "Starter", status: "trial" as const, accounts: 1, posts: 12, joined: "2026-03-18" },
  { id: 4, name: "James O'Brien", email: "james.obrien@adwave.io", avatar: null, plan: "Professional", status: "active" as const, accounts: 4, posts: 734, joined: "2025-08-05" },
  { id: 5, name: "Aisha Mohammed", email: "aisha@brandpulse.co", avatar: null, plan: "Starter", status: "trial" as const, accounts: 1, posts: 5, joined: "2026-03-22" },
  { id: 6, name: "David Kim", email: "david.kim@nexusdigital.io", avatar: null, plan: "Enterprise", status: "active" as const, accounts: 12, posts: 2890, joined: "2024-11-10" },
  { id: 7, name: "Emma Rodriguez", email: "emma@socialcraft.co", avatar: null, plan: "Professional", status: "suspended" as const, accounts: 2, posts: 367, joined: "2025-09-17" },
  { id: 8, name: "Liam Thompson", email: "liam@pixelreach.com", avatar: null, plan: "Starter", status: "active" as const, accounts: 1, posts: 89, joined: "2026-01-03" },
  { id: 9, name: "Sofia Nakamura", email: "sofia@zenithcm.io", avatar: null, plan: "Professional", status: "active" as const, accounts: 5, posts: 1102, joined: "2025-04-28" },
  { id: 10, name: "Oliver Becker", email: "oliver@marketedge.de", avatar: null, plan: "Enterprise", status: "active" as const, accounts: 6, posts: 1567, joined: "2025-01-15" },
  { id: 11, name: "Ava Martinez", email: "ava@buzzstream.co", avatar: null, plan: "Professional", status: "active" as const, accounts: 3, posts: 621, joined: "2025-07-22" },
  { id: 12, name: "Noah Johnson", email: "noah@sparkdigital.com", avatar: null, plan: "Starter", status: "trial" as const, accounts: 1, posts: 3, joined: "2026-03-26" },
  { id: 13, name: "Mia Chang", email: "mia.chang@orbitcm.io", avatar: null, plan: "Enterprise", status: "active" as const, accounts: 10, posts: 3420, joined: "2024-09-01" },
  { id: 14, name: "Ethan Murphy", email: "ethan@reachfactory.co", avatar: null, plan: "Professional", status: "suspended" as const, accounts: 2, posts: 215, joined: "2025-11-30" },
  { id: 15, name: "Isabella Torres", email: "isabella@contentpro.mx", avatar: null, plan: "Starter", status: "active" as const, accounts: 1, posts: 44, joined: "2026-02-14" },
];

type UserStatus = "active" | "suspended" | "trial";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [openDropdown, setOpenDropdown] = useState<number | null>(null);

  const perPage = 20;

  const filtered = mockUsers.filter((u) => {
    const matchesSearch =
      search === "" ||
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase());
    const matchesPlan = planFilter === "all" || u.plan === planFilter;
    const matchesStatus = statusFilter === "all" || u.status === statusFilter;
    return matchesSearch && matchesPlan && matchesStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated = filtered.slice((page - 1) * perPage, page * perPage);

  const planBadge = (plan: string) => {
    if (plan === "Enterprise") return "warning";
    if (plan === "Professional") return "info";
    return "default";
  };

  const statusBadge = (status: UserStatus) => {
    if (status === "active") return "success";
    if (status === "trial") return "info";
    return "danger";
  };

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeUp} className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center">
              <Users className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--page-heading)" }}>User Management</h1>
              <p className="text-sm tabular-nums" style={{ color: "var(--page-text-secondary)" }}>{formatNumber(mockUsers.length)} total users</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="secondary" size="sm" icon={<Download className="w-4 h-4" />}>
              Export
            </Button>
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div variants={fadeUp} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 max-w-md">
            <Input
              placeholder="Search users..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="flex gap-3">
            <div className="relative">
              <select
                value={planFilter}
                onChange={(e) => { setPlanFilter(e.target.value); setPage(1); }}
                className="appearance-none backdrop-blur-sm rounded-xl px-4 py-3 pr-10 text-sm outline-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)] focus:border-[rgba(124,58,237,0.50)] transition-all cursor-pointer"
                style={{ border: "1px solid var(--surface-border)", backgroundColor: "var(--input-bg)", color: "var(--page-text)" }}
              >
                <option value="all" style={{ backgroundColor: "var(--surface-bg)" }}>All Plans</option>
                <option value="Starter" style={{ backgroundColor: "var(--surface-bg)" }}>Starter</option>
                <option value="Professional" style={{ backgroundColor: "var(--surface-bg)" }}>Professional</option>
                <option value="Enterprise" style={{ backgroundColor: "var(--surface-bg)" }}>Enterprise</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: "var(--page-text-secondary)" }} />
            </div>

            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="appearance-none backdrop-blur-sm rounded-xl px-4 py-3 pr-10 text-sm outline-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)] focus:border-[rgba(124,58,237,0.50)] transition-all cursor-pointer"
                style={{ border: "1px solid var(--surface-border)", backgroundColor: "var(--input-bg)", color: "var(--page-text)" }}
              >
                <option value="all" style={{ backgroundColor: "var(--surface-bg)" }}>All Statuses</option>
                <option value="active" style={{ backgroundColor: "var(--surface-bg)" }}>Active</option>
                <option value="trial" style={{ backgroundColor: "var(--surface-bg)" }}>Trial</option>
                <option value="suspended" style={{ backgroundColor: "var(--surface-bg)" }}>Suspended</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: "var(--page-text-secondary)" }} />
            </div>
          </div>
        </motion.div>

        {/* Users Table */}
        <motion.div variants={fadeUp}>
          <GlassCard padding="sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                    <th className="text-left font-medium py-3 px-4" style={{ color: "var(--page-text-muted)" }}>User</th>
                    <th className="text-left font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Email</th>
                    <th className="text-left font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Plan</th>
                    <th className="text-left font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Status</th>
                    <th className="text-center font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Accounts</th>
                    <th className="text-center font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Posts</th>
                    <th className="text-left font-medium py-3 px-3" style={{ color: "var(--page-text-muted)" }}>Joined</th>
                    <th className="text-right font-medium py-3 px-4" style={{ color: "var(--page-text-muted)" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((user) => (
                    <motion.tr
                      key={user.id}
                      layout
                      className={cn(
                        "last:border-0 transition-colors cursor-pointer",
                        expandedId === user.id ? "bg-[var(--sidebar-hover-bg)]" : "hover:bg-[var(--sidebar-hover-bg)]"
                      )}
                      style={{ borderBottom: "1px solid var(--surface-border)" }}
                      onClick={() => setExpandedId(expandedId === user.id ? null : user.id)}
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/20 flex items-center justify-center text-xs font-semibold text-purple-300 flex-shrink-0">
                            {user.name.split(" ").map((n) => n[0]).join("")}
                          </div>
                          <span className="font-medium whitespace-nowrap" style={{ color: "var(--page-heading)" }}>{user.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap" style={{ color: "var(--page-text-secondary)" }}>{user.email}</td>
                      <td className="py-3 px-3">
                        <Badge variant={planBadge(user.plan)} size="sm">{user.plan}</Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={statusBadge(user.status)} dot size="sm">
                          {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-center tabular-nums" style={{ color: "var(--page-text)" }}>{user.accounts}</td>
                      <td className="py-3 px-3 text-center tabular-nums" style={{ color: "var(--page-text)" }}>{formatNumber(user.posts)}</td>
                      <td className="py-3 px-3 whitespace-nowrap tabular-nums" style={{ color: "var(--page-text-secondary)" }}>{formatDate(user.joined)}</td>
                      <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="relative inline-block">
                          <button
                            onClick={() => setOpenDropdown(openDropdown === user.id ? null : user.id)}
                            className="p-1.5 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-colors text-[var(--page-text-secondary)] hover:text-[var(--page-heading)] cursor-pointer"
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </button>

                          <AnimatePresence>
                            {openDropdown === user.id && (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95, y: -4 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95, y: -4 }}
                                transition={{ duration: 0.12 }}
                                className="absolute right-0 top-full mt-1 z-50 w-48 rounded-xl backdrop-blur-xl p-1.5 shadow-xl shadow-black/40"
                                style={{ backgroundColor: "var(--surface-bg)", border: "1px solid var(--surface-border)" }}
                              >
                                <button className="w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-colors hover:bg-[var(--sidebar-hover-bg)] cursor-pointer" style={{ color: "var(--page-text)" }}>
                                  <Eye className="w-4 h-4" /> View Details
                                </button>
                                <button className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-amber-400 hover:bg-amber-500/10 rounded-lg transition-colors cursor-pointer">
                                  <UserCog className="w-4 h-4" /> Impersonate
                                </button>
                                <button className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-orange-400 hover:bg-orange-500/10 rounded-lg transition-colors cursor-pointer">
                                  <Ban className="w-4 h-4" /> {user.status === "suspended" ? "Unsuspend" : "Suspend"}
                                </button>
                                <div className="my-1" style={{ borderTop: "1px solid var(--surface-border)" }} />
                                <button className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer">
                                  <Trash2 className="w-4 h-4" /> Delete User
                                </button>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Expanded user details - rendered outside the table for proper layout */}
            <AnimatePresence>
              {expandedId && (() => {
                const user = mockUsers.find((u) => u.id === expandedId);
                if (!user) return null;
                return (
                  <motion.div
                    key={`expanded-${user.id}`}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden"
                    style={{ borderTop: "1px solid var(--surface-border)" }}
                  >
                    <div className="p-5 grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="flex items-center gap-2.5">
                        <Mail className="w-4 h-4" style={{ color: "var(--page-text-muted)" }} />
                        <div>
                          <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>Email</p>
                          <p className="text-sm" style={{ color: "var(--page-text)" }}>{user.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <Calendar className="w-4 h-4" style={{ color: "var(--page-text-muted)" }} />
                        <div>
                          <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>Joined</p>
                          <p className="text-sm tabular-nums" style={{ color: "var(--page-text)" }}>{formatDate(user.joined)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <Building2 className="w-4 h-4" style={{ color: "var(--page-text-muted)" }} />
                        <div>
                          <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>Accounts</p>
                          <p className="text-sm tabular-nums" style={{ color: "var(--page-text)" }}>{user.accounts} connected</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <FileText className="w-4 h-4" style={{ color: "var(--page-text-muted)" }} />
                        <div>
                          <p className="text-[11px] font-medium" style={{ color: "var(--page-text-muted)" }}>Posts</p>
                          <p className="text-sm tabular-nums" style={{ color: "var(--page-text)" }}>{formatNumber(user.posts)} published</p>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })()}
            </AnimatePresence>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: "1px solid var(--surface-border)" }}>
              <p className="text-sm tabular-nums" style={{ color: "var(--page-text-secondary)" }}>
                Showing {((page - 1) * perPage) + 1}-{Math.min(page * perPage, filtered.length)} of {filtered.length} users
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="p-2 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-colors text-[var(--page-text-secondary)] hover:text-[var(--page-heading)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={cn(
                      "w-8 h-8 rounded-lg text-sm font-medium transition-colors tabular-nums cursor-pointer",
                      p === page
                        ? ""
                        : "text-[var(--page-text-muted)] hover:bg-[var(--sidebar-hover-bg)] hover:text-[var(--page-heading)]"
                    )}
                    style={p === page ? { background: "rgba(124,58,237,0.14)", border: "1px solid rgba(124,58,237,0.30)", color: "var(--page-heading)" } : undefined}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="p-2 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-colors text-[var(--page-text-secondary)] hover:text-[var(--page-heading)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </GlassCard>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
