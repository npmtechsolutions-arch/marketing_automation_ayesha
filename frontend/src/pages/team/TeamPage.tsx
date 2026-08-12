import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
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
  Loader2,
  AlertCircle,
  Clock,
  Copy,
  Link,
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
import api, { getAccountId } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────
type Role = "owner" | "admin" | "manager" | "editor" | "viewer";
type InvitationStatus = "pending" | "accepted" | "declined" | "expired";

interface TeamMember {
  id: string;
  user_id: string | null;
  account_id: string;
  role: Role;
  invitation_email: string | null;
  invitation_status: InvitationStatus;
  invited_by: string | null;
  created_at: string;
  accepted_at: string | null;
  user?: {
    id: string;
    email: string;
    full_name: string | null;
  } | null;
}

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
  const navigate = useNavigate();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showPermissions, setShowPermissions] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);
  const [newRole, setNewRole] = useState("editor");
  const [updatingRole, setUpdatingRole] = useState(false);

  const [removingId, setRemovingId] = useState<string | null>(null);

  const activeMembers = members.filter((m) => m.invitation_status === "accepted");
  const pendingMembers = members.filter((m) => m.invitation_status === "pending");

  // ── Load members ──────────────────────────────────────────────────
  const loadMembers = useCallback(async () => {
    setLoading(true);
    setError(null);
    const accountId = await getAccountId();
    if (!accountId) {
      setLoading(false);
      setError("Could not determine your account. Please refresh the page.");
      return;
    }
    try {
      const res: any = await api.get(`/accounts/${accountId}/team/?per_page=100`);
      const payload = res.data ?? res;
      const items: TeamMember[] = payload.items ?? payload ?? [];
      setMembers(items);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Failed to load team members.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setInviteError(null);
    const accountId = await getAccountId();
    if (!accountId) {
      setInviteError("Could not determine your account.");
      setInviting(false);
      return;
    }
    try {
      const res: any = await api.post(`/accounts/${accountId}/team/invite`, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      const payload = res.data ?? res;
      const token = payload.invitation_token;
      if (token && accountId) {
        const baseUrl = window.location.origin;
        setInviteLink(
          `${baseUrl}/accept-invite?account=${accountId}&token=${token}`
        );
      } else {
        setInviteLink(null);
      }
      setInviteSuccess(true);
      await loadMembers();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setInviteError(typeof detail === "string" ? detail : "Failed to send invitation. Please try again.");
    } finally {
      setInviting(false);
    }
  };

  const copyLink = () => {
    if (!inviteLink) return;
    navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setInviteEmail("");
    setInviteRole("editor");
    setInviteError(null);
    setInviteSuccess(false);
    setInviteLink(null);
    setCopied(false);
  };

  // ── Update role ───────────────────────────────────────────────────
  const openRoleModal = (member: TeamMember) => {
    setSelectedMember(member);
    setNewRole(member.role);
    setShowRoleModal(true);
    setOpenDropdown(null);
  };

  const handleUpdateRole = async () => {
    if (!selectedMember) return;
    setUpdatingRole(true);
    const accountId = await getAccountId();
    if (!accountId) { setUpdatingRole(false); return; }
    try {
      await api.put(`/accounts/${accountId}/team/${selectedMember.id}`, { role: newRole });
      await loadMembers();
      setShowRoleModal(false);
      setSelectedMember(null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      alert(typeof detail === "string" ? detail : "Failed to update role.");
    } finally {
      setUpdatingRole(false);
    }
  };

  // ── Remove member ─────────────────────────────────────────────────
  const handleRemove = async (member: TeamMember) => {
    if (!confirm(`Remove ${member.user?.full_name || member.invitation_email || "this member"} from the team?`)) return;
    setRemovingId(member.id);
    setOpenDropdown(null);
    const accountId = await getAccountId();
    if (!accountId) { setRemovingId(null); return; }
    try {
      await api.delete(`/accounts/${accountId}/team/${member.id}`);
      await loadMembers();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      alert(typeof detail === "string" ? detail : "Failed to remove member.");
    } finally {
      setRemovingId(null);
    }
  };

  const getMemberName = (m: TeamMember) =>
    m.user?.full_name || m.invitation_email?.split("@")[0] || "Unknown";
  const getMemberEmail = (m: TeamMember) =>
    m.user?.email || m.invitation_email || "—";

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center justify-between"
        >
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl" style={{ color: "var(--page-heading)" }}>Team</h1>
              <Badge variant="default">{members.length} members</Badge>
            </div>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>Manage your team members and permissions</p>
          </div>
          <Button
            variant="primary"
            icon={<UserPlus className="w-4 h-4" />}
            onClick={() => { setShowInviteModal(true); setInviteError(null); setInviteSuccess(false); }}
          >
            Invite Member
          </Button>
        </motion.div>

        {/* Plan Info */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }}>
          <GlassCard>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center">
                  <Users className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>
                    {activeMembers.length} of {planLimit} team members used
                  </p>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>Growth Plan</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-48 h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--sidebar-hover-bg)" }}>
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-700"
                    style={{ width: `${Math.min((activeMembers.length / planLimit) * 100, 100)}%` }}
                  />
                </div>
                <Button variant="ghost" size="sm" icon={<ArrowUpRight className="w-3.5 h-3.5" />} iconPosition="right" onClick={() => navigate("/billing")}>
                  Upgrade
                </Button>
              </div>
            </div>
          </GlassCard>
        </motion.div>

        {/* ── How to Invite Instructions ────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 0.5 }}>
          <GlassCard className="border-purple-500/20 bg-purple-500/5">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600/30 to-blue-600/30 border border-purple-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Info className="w-5 h-5 text-purple-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-white mb-3">How to Invite a Team Member</h3>
                <div className="space-y-3">
                  {/* Step 1 */}
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-bold text-purple-300">1</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>Click "Invite Member"</p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--page-text-secondary)" }}>
                        Click the <strong className="text-purple-300">Invite Member</strong> button at the top-right of this page. Enter the person's email address and choose their role (Admin, Manager, Editor, or Viewer).
                      </p>
                    </div>
                  </div>
                  {/* Step 2 */}
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-bold text-blue-300">2</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>Copy the Invitation Link</p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--page-text-secondary)" }}>
                        After sending, an <strong style={{ color: "var(--page-heading)" }}>invitation link</strong> will appear on screen. Click <strong className="text-purple-300">"Copy Invitation Link"</strong> and send it to your team member via WhatsApp, email, or any messaging app.
                      </p>
                    </div>
                  </div>
                  {/* Step 3 */}
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-bold text-emerald-300">3</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--page-heading)" }}>Team Member Registers & Accepts</p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--page-text-secondary)" }}>
                        The invited person must first <strong style={{ color: "var(--page-heading)" }}>register an account</strong> at this app using the <strong style={{ color: "var(--page-heading)" }}>same email address</strong> you invited. After registering and logging in, they open the invitation link — they will be added to your team automatically.
                      </p>
                    </div>
                  </div>
                  {/* Note */}
                  <div className="flex items-start gap-2 mt-1 pt-3" style={{ borderTop: "1px solid var(--surface-border)" }}>
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-400/80">
                      <strong>Note:</strong> No automatic email is sent. You must manually share the invitation link with the person. Pending invitations are shown below until they accept.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </GlassCard>
        </motion.div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
            <span className="ml-3" style={{ color: "var(--page-text-secondary)" }}>Loading team members…</span>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <GlassCard className="border-red-500/20">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm">{error}</p>
              <Button variant="ghost" size="sm" onClick={loadMembers} className="ml-auto">
                <RefreshCw className="w-4 h-4 mr-1" /> Retry
              </Button>
            </div>
          </GlassCard>
        )}

        {/* Active Members */}
        {!loading && !error && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium uppercase tracking-wider px-1" style={{ color: "var(--page-text-muted)" }}>
              Active Members ({activeMembers.length})
            </h2>

            {activeMembers.length === 0 && (
              <GlassCard>
                <div className="text-center py-8">
                  <Users className="w-10 h-10 mx-auto mb-3" style={{ color: "var(--page-text-muted)", opacity: 0.6 }} />
                  <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>No active members yet.</p>
                  <p className="text-xs mt-1" style={{ color: "var(--page-text-muted)" }}>Invite your first team member to get started.</p>
                </div>
              </GlassCard>
            )}

            {activeMembers.map((member, idx) => {
              const role = roleConfig[member.role] ?? roleConfig.viewer;
              const isRemoving = removingId === member.id;
              return (
                <motion.div
                  key={member.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: isRemoving ? 0.4 : 1, y: 0 }}
                  transition={{ delay: 0.1 + idx * 0.05, duration: 0.4 }}
                >
                  <GlassCard hover padding="sm">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <Avatar name={getMemberName(member)} size="lg" online />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium" style={{ color: "var(--page-heading)" }}>{getMemberName(member)}</p>
                            {member.role === "owner" && <Crown className="w-4 h-4 text-amber-400" />}
                          </div>
                          <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>{getMemberEmail(member)}</p>
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
                              className="p-2 rounded-lg hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                              style={{ color: "var(--page-text-muted)" }}
                              disabled={isRemoving}
                            >
                              {isRemoving
                                ? <Loader2 className="w-4 h-4 animate-spin" />
                                : <MoreVertical className="w-4 h-4" />}
                            </button>
                            <AnimatePresence>
                              {openDropdown === member.id && (
                                <motion.div
                                  initial={{ opacity: 0, scale: 0.95, y: -4 }}
                                  animate={{ opacity: 1, scale: 1, y: 0 }}
                                  exit={{ opacity: 0, scale: 0.95, y: -4 }}
                                  transition={{ duration: 0.15 }}
                                  className="absolute right-0 top-full mt-1 w-48 rounded-xl backdrop-blur-xl p-1.5 shadow-xl z-50"
                                  style={{ backgroundColor: "var(--surface-bg)", border: "1px solid var(--surface-border)" }}
                                >
                                  <button
                                    onClick={() => openRoleModal(member)}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors cursor-pointer hover:bg-[var(--sidebar-hover-bg)]"
                                    style={{ color: "var(--page-text)" }}
                                  >
                                    <Shield className="w-4 h-4" /> Change Role
                                  </button>
                                  <button
                                    onClick={() => handleRemove(member)}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                  >
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
        )}

        {/* Pending Invitations */}
        {!loading && !error && pendingMembers.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium uppercase tracking-wider px-1" style={{ color: "var(--page-text-muted)" }}>
              Pending Invitations ({pendingMembers.length})
            </h2>
            {pendingMembers.map((member, idx) => {
              const role = roleConfig[member.role] ?? roleConfig.viewer;
              const isRemoving = removingId === member.id;
              return (
                <motion.div
                  key={member.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: isRemoving ? 0.4 : 1, y: 0 }}
                  transition={{ delay: 0.3 + idx * 0.05, duration: 0.4 }}
                >
                  <GlassCard padding="sm" className="!border-dashed !border-[var(--surface-border)]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                          <Clock className="w-5 h-5 text-amber-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium" style={{ color: "var(--page-heading)" }}>{getMemberEmail(member)}</p>
                            <Badge variant="warning" size="sm">Pending</Badge>
                          </div>
                          <p className="text-xs mt-0.5" style={{ color: "var(--page-text-muted)" }}>
                            Invited {new Date(member.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border", role.color, role.bg, role.border)}>
                          {role.label}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={isRemoving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
                          className="text-red-400 hover:text-red-300"
                          onClick={() => handleRemove(member)}
                          disabled={isRemoving}
                        >
                          Cancel
                        </Button>
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
                <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>Role Permissions</h3>
              </div>
              <ChevronDown className={cn("w-5 h-5 transition-transform duration-300", showPermissions && "rotate-180")} style={{ color: "var(--page-text-muted)" }} />
            </button>
            <AnimatePresence>
              {showPermissions && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden"
                >
                  <div className="mt-5 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--surface-border)" }}>
                          <th className="text-left font-medium py-3 pr-4 min-w-[200px]" style={{ color: "var(--page-text-muted)" }}>Permission</th>
                          {(["owner", "admin", "manager", "editor", "viewer"] as Role[]).map((r) => (
                            <th key={r} className="text-center py-3 px-3">
                              <span className={cn("text-xs font-medium", roleConfig[r].color)}>{roleConfig[r].label}</span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {permissions.map((perm, idx) => (
                          <tr key={idx} style={{ borderBottom: "1px solid var(--surface-border)" }}>
                            <td className="py-3 pr-4" style={{ color: "var(--page-text)" }}>{perm.label}</td>
                            {(["owner", "admin", "manager", "editor", "viewer"] as Role[]).map((r) => (
                              <td key={r} className="text-center py-3 px-3">
                                {perm[r] ? (
                                  <Check className="w-4 h-4 text-emerald-400 mx-auto" />
                                ) : (
                                  <X className="w-4 h-4 mx-auto" style={{ color: "var(--page-text-muted)", opacity: 0.5 }} />
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
      </div>

      {/* ── Invite Member Modal ─────────────────────────────────────── */}
      <Modal
        isOpen={showInviteModal}
        onClose={closeInviteModal}
        title="Invite Team Member"
        size="md"
      >
        <div className="space-y-5">
          {inviteSuccess ? (
            <div className="space-y-4">
              <div className="flex flex-col items-center py-4 gap-3">
                <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                  <Check className="w-7 h-7 text-emerald-400" />
                </div>
                <p className="font-semibold" style={{ color: "var(--page-heading)" }}>Invitation Created!</p>
                <p className="text-sm text-center" style={{ color: "var(--page-text-secondary)" }}>
                  Share this link with <strong style={{ color: "var(--page-heading)" }}>{inviteEmail}</strong> so they can join your team.
                </p>
              </div>

              {inviteLink ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 p-3 rounded-xl" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                    <Link className="w-4 h-4 text-purple-400 flex-shrink-0" />
                    <p className="text-xs flex-1 break-all font-mono" style={{ color: "var(--page-text)" }}>{inviteLink}</p>
                  </div>
                  <button
                    onClick={copyLink}
                    className={cn(
                      "w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                      copied
                        ? "bg-emerald-500/20 border border-emerald-500/30 text-emerald-400"
                        : "bg-purple-600/20 border border-purple-500/30 text-purple-300 hover:bg-purple-600/30"
                    )}
                  >
                    {copied ? (
                      <><Check className="w-4 h-4" /> Copied!</>
                    ) : (
                      <><Copy className="w-4 h-4" /> Copy Invitation Link</>
                    )}
                  </button>
                  <p className="text-xs text-center" style={{ color: "var(--page-text-muted)" }}>
                    ⚠️ The invitee must already have an account or sign up first, then visit this link.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-center" style={{ color: "var(--page-text-muted)" }}>
                  Invitation recorded. The invitee will appear in Pending until they accept.
                </p>
              )}

              <div className="flex justify-end pt-1">
                <Button variant="ghost" onClick={closeInviteModal}>Close</Button>
              </div>
            </div>
          ) : (
            <>
              <Input
                label="Email Address"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                icon={<Mail className="w-4 h-4" />}
                onKeyDown={(e) => e.key === "Enter" && !inviting && inviteEmail && handleInvite()}
              />

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
                <div className="p-3 rounded-xl" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                  <p className="text-xs" style={{ color: "var(--page-text-secondary)" }}>{roleDescriptions[inviteRole as Exclude<Role, "owner">]}</p>
                </div>
              )}

              {inviteError && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <p className="text-sm text-red-400">{inviteError}</p>
                </div>
              )}

              <div className="flex gap-3 justify-end pt-2">
                <Button
                  variant="ghost"
                  onClick={closeInviteModal}
                  disabled={inviting}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  icon={inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                  disabled={!inviteEmail.trim() || inviting}
                  onClick={handleInvite}
                >
                  {inviting ? "Sending…" : "Send Invitation"}
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* ── Change Role Modal ───────────────────────────────────────── */}
      <Modal
        isOpen={showRoleModal}
        onClose={() => { setShowRoleModal(false); setSelectedMember(null); }}
        title="Change Member Role"
        size="sm"
      >
        {selectedMember && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-xl" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
              <Avatar name={getMemberName(selectedMember)} size="md" />
              <div>
                <p className="font-medium text-sm" style={{ color: "var(--page-heading)" }}>{getMemberName(selectedMember)}</p>
                <p className="text-xs" style={{ color: "var(--page-text-secondary)" }}>{getMemberEmail(selectedMember)}</p>
              </div>
            </div>

            <Select
              label="New Role"
              options={[
                { value: "admin", label: "Admin" },
                { value: "manager", label: "Manager" },
                { value: "editor", label: "Editor" },
                { value: "viewer", label: "Viewer" },
              ]}
              value={newRole}
              onChange={setNewRole}
            />

            {newRole && newRole !== "owner" && (
              <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                <p className="text-xs text-gray-400">{roleDescriptions[newRole as Exclude<Role, "owner">]}</p>
              </div>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <Button variant="ghost" onClick={() => { setShowRoleModal(false); setSelectedMember(null); }} disabled={updatingRole}>
                Cancel
              </Button>
              <Button
                variant="primary"
                icon={updatingRole ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                disabled={updatingRole || newRole === selectedMember.role}
                onClick={handleUpdateRole}
              >
                {updatingRole ? "Updating…" : "Update Role"}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Click-away overlay for dropdown */}
      {openDropdown && (
        <div className="fixed inset-0 z-40" onClick={() => setOpenDropdown(null)} />
      )}
    </DashboardLayout>
  );
}
