import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  UserPlus,
  MoreVertical,
  Mail,
  Shield,
  Crown,
  Trash2,
  RefreshCw,
  X,
  ChevronDown,
  Check,
  ArrowUpRight,
  Info,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { Select } from "@/components/ui/Select";
import { cn } from "@/lib/utils";

// ── Types ───────────────────────────────────────────────────────────
type Role = "owner" | "admin" | "manager" | "editor" | "viewer";
type MemberStatus = "active" | "pending";

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: MemberStatus;
  avatar: string | null;
  joinedAt: string;
}

// ── Mock Data ───────────────────────────────────────────────────────
const mockMembers: TeamMember[] = [
  { id: "1", name: "Alex Thompson", email: "alex@visionaryspace.io", role: "owner", status: "active", avatar: null, joinedAt: "2024-01-15" },
  { id: "2", name: "Sarah Chen", email: "sarah@visionaryspace.io", role: "admin", status: "active", avatar: null, joinedAt: "2024-03-20" },
  { id: "3", name: "Marcus Johnson", email: "marcus@visionaryspace.io", role: "manager", status: "active", avatar: null, joinedAt: "2024-06-10" },
  { id: "4", name: "Emily Rodriguez", email: "emily@visionaryspace.io", role: "editor", status: "active", avatar: null, joinedAt: "2024-08-05" },
  { id: "5", name: "James Wilson", email: "james@visionaryspace.io", role: "viewer", status: "active", avatar: null, joinedAt: "2025-01-12" },
  { id: "6", name: "Olivia Park", email: "olivia@example.com", role: "editor", status: "pending", avatar: null, joinedAt: "2026-03-25" },
  { id: "7", name: "David Kim", email: "david@example.com", role: "viewer", status: "pending", avatar: null, joinedAt: "2026-03-28" },
];

const roleConfig: Record<Role, { label: string; color: string; bg: string; border: string }> = {
  owner: { label: "Owner", color: "text-purple-300", bg: "bg-purple-500/10", border: "border-purple-500/20" },
  admin: { label: "Admin", color: "text-blue-300", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  manager: { label: "Manager", color: "text-emerald-300", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  editor: { label: "Editor", color: "text-amber-300", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  viewer: { label: "Viewer", color: "text-gray-300", bg: "bg-white/5", border: "border-white/10" },
};

const roleDescriptions: Record<Exclude<Role, "owner">, string> = {
  admin: "Full access to all features, team management, and billing",
  manager: "Create, edit, and schedule content across all platforms",
  editor: "Create and edit content, but cannot publish or manage team",
  viewer: "View-only access to content, analytics, and reports",
};

const permissions = [
  { label: "View dashboard & analytics", owner: true, admin: true, manager: true, editor: true, viewer: true },
  { label: "Create & edit content", owner: true, admin: true, manager: true, editor: true, viewer: false },
  { label: "Publish & schedule posts", owner: true, admin: true, manager: true, editor: false, viewer: false },
  { label: "Manage campaigns", owner: true, admin: true, manager: true, editor: false, viewer: false },
  { label: "View team members", owner: true, admin: true, manager: true, editor: true, viewer: true },
  { label: "Invite & remove members", owner: true, admin: true, manager: false, editor: false, viewer: false },
  { label: "Manage connected platforms", owner: true, admin: true, manager: false, editor: false, viewer: false },
  { label: "Access billing & subscription", owner: true, admin: true, manager: false, editor: false, viewer: false },
  { label: "Change workspace settings", owner: true, admin: false, manager: false, editor: false, viewer: false },
  { label: "Transfer or delete workspace", owner: true, admin: false, manager: false, editor: false, viewer: false },
];

const planLimit = 10;

// ── Component ───────────────────────────────────────────────────────

export default function TeamPage() {
  const [members] = useState(mockMembers);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showPermissions, setShowPermissions] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  const activeMembers = members.filter((m) => m.status === "active");
  const pendingMembers = members.filter((m) => m.status === "pending");

  return (
    <DashboardLayout>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white">Team</h1>
            <Badge variant="default">{members.length} members</Badge>
          </div>
          <p className="text-gray-400 mt-1">Manage your team members and permissions</p>
        </div>
        <Button variant="primary" icon={<UserPlus className="w-4 h-4" />} onClick={() => setShowInviteModal(true)}>
          Invite Member
        </Button>
      </motion.div>

      {/* Plan Info */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }}>
        <GlassCard className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center">
                <Users className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-white font-medium">{members.length} of {planLimit} team members used</p>
                <p className="text-xs text-gray-400">Growth Plan</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-48 h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-purple-500 to-blue-500"
                  style={{ width: `${(members.length / planLimit) * 100}%` }}
                />
              </div>
              <Button variant="ghost" size="sm" icon={<ArrowUpRight className="w-3.5 h-3.5" />} iconPosition="right">
                Upgrade
              </Button>
            </div>
          </div>
        </GlassCard>
      </motion.div>

      {/* Active Members */}
      <div className="space-y-3 mb-8">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider px-1">Active Members ({activeMembers.length})</h2>
        {activeMembers.map((member, idx) => {
          const role = roleConfig[member.role];
          return (
            <motion.div key={member.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + idx * 0.05, duration: 0.4 }}>
              <GlassCard hover padding="sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <Avatar name={member.name} size="lg" online />
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-white font-medium">{member.name}</p>
                        {member.role === "owner" && <Crown className="w-4 h-4 text-amber-400" />}
                      </div>
                      <p className="text-sm text-gray-400">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border", role.color, role.bg, role.border)}>
                      {role.label}
                    </span>
                    <Badge variant="success" dot size="sm">Active</Badge>
                    {member.role !== "owner" && (
                      <div className="relative">
                        <button
                          onClick={() => setOpenDropdown(openDropdown === member.id ? null : member.id)}
                          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                        <AnimatePresence>
                          {openDropdown === member.id && (
                            <motion.div
                              initial={{ opacity: 0, scale: 0.95, y: -4 }}
                              animate={{ opacity: 1, scale: 1, y: 0 }}
                              exit={{ opacity: 0, scale: 0.95, y: -4 }}
                              transition={{ duration: 0.15 }}
                              className="absolute right-0 top-full mt-1 w-48 rounded-xl bg-slate-900/95 backdrop-blur-xl border border-white/10 p-1.5 shadow-xl z-50"
                            >
                              <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-300 hover:bg-white/10 rounded-lg transition-colors">
                                <Shield className="w-4 h-4" /> Change Role
                              </button>
                              <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                                <Trash2 className="w-4 h-4" /> Remove Member
                              </button>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>

      {/* Pending Invitations */}
      {pendingMembers.length > 0 && (
        <div className="space-y-3 mb-8">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider px-1">Pending Invitations ({pendingMembers.length})</h2>
          {pendingMembers.map((member, idx) => {
            const role = roleConfig[member.role];
            return (
              <motion.div key={member.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + idx * 0.05, duration: 0.4 }}>
                <GlassCard padding="sm" className="!border-dashed !border-white/15">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <Avatar name={member.name} size="lg" />
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-white font-medium">{member.name}</p>
                          <Badge variant="warning" size="sm">Invitation Pending</Badge>
                        </div>
                        <p className="text-sm text-gray-400">{member.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border", role.color, role.bg, role.border)}>
                        {role.label}
                      </span>
                      <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />}>Resend</Button>
                      <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300" icon={<X className="w-3.5 h-3.5" />}>Cancel</Button>
                    </div>
                  </div>
                </GlassCard>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Role Permissions */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.5 }}>
        <GlassCard>
          <button onClick={() => setShowPermissions(!showPermissions)} className="w-full flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Info className="w-5 h-5 text-purple-400" />
              <h3 className="text-base font-semibold text-white">Role Permissions</h3>
            </div>
            <ChevronDown className={cn("w-5 h-5 text-gray-400 transition-transform duration-300", showPermissions && "rotate-180")} />
          </button>
          <AnimatePresence>
            {showPermissions && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
                <div className="mt-5 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left text-gray-400 font-medium py-3 pr-4 min-w-[200px]">Permission</th>
                        {(["owner", "admin", "manager", "editor", "viewer"] as Role[]).map((r) => (
                          <th key={r} className="text-center py-3 px-3">
                            <span className={cn("text-xs font-medium", roleConfig[r].color)}>{roleConfig[r].label}</span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {permissions.map((perm, idx) => (
                        <tr key={idx} className="border-b border-white/5">
                          <td className="py-3 pr-4 text-gray-300">{perm.label}</td>
                          {(["owner", "admin", "manager", "editor", "viewer"] as Role[]).map((r) => (
                            <td key={r} className="text-center py-3 px-3">
                              {perm[r] ? (
                                <Check className="w-4 h-4 text-emerald-400 mx-auto" />
                              ) : (
                                <X className="w-4 h-4 text-gray-600 mx-auto" />
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </GlassCard>
      </motion.div>

      {/* Invite Member Modal */}
      <Modal isOpen={showInviteModal} onClose={() => { setShowInviteModal(false); setInviteEmail(""); setInviteRole("editor"); }} title="Invite Team Member" size="md">
        <div className="space-y-5">
          <Input label="Email Address" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="colleague@company.com" icon={<Mail className="w-4 h-4" />} />

          <Select
            label="Role"
            options={[
              { value: "admin", label: "Admin" },
              { value: "manager", label: "Manager" },
              { value: "editor", label: "Editor" },
              { value: "viewer", label: "Viewer" },
            ]}
            value={inviteRole}
            onChange={setInviteRole}
          />

          {inviteRole && inviteRole !== "owner" && (
            <div className="p-3 rounded-xl bg-white/5 border border-white/10">
              <p className="text-xs text-gray-400">{roleDescriptions[inviteRole as Exclude<Role, "owner">]}</p>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2">
            <Button variant="ghost" onClick={() => { setShowInviteModal(false); setInviteEmail(""); setInviteRole("editor"); }}>Cancel</Button>
            <Button variant="primary" icon={<UserPlus className="w-4 h-4" />} disabled={!inviteEmail}>Send Invitation</Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
