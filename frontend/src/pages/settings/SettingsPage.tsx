import { useState, useEffect, useRef, useCallback, type JSX } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  User,
  Lock,
  Bell,
  Building2,
  Palette,
  Camera,
  Shield,
  Copy,
  Eye,
  EyeOff,
  Check,
  AlertTriangle,
  Moon,
  Sun,
  PanelLeftClose,
  PanelLeft,
  LayoutDashboard,
  CalendarDays,
  Loader2,
  Monitor,
  Trash2,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { Select } from "@/components/ui/Select";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { useAuthStore } from "@/stores/authStore";
import api, { get, put, post, del, getAccountId } from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";

// ── Settings nav items ──────────────────────────────────────────────
const settingsNav = [
  { id: "profile", label: "Profile", icon: User },
  { id: "security", label: "Password & Security", icon: Lock },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "business", label: "Business Profile", icon: Building2 },
  { id: "appearance", label: "Appearance", icon: Palette },
] as const;

type SettingsTab = (typeof settingsNav)[number]["id"];

const emailNotifDefaults = {
  postPublished: true,
  postFailed: true,
  weeklyReport: true,
  strategyRecommendations: false,
  teamInvitations: true,
  billingAlerts: true,
};

const inAppNotifDefaults = {
  postPublished: true,
  postFailed: true,
  weeklyReport: false,
  strategyRecommendations: true,
  teamInvitations: true,
  billingAlerts: true,
};

const industryOptions = [
  { value: "saas", label: "SaaS / Technology" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "agency", label: "Marketing Agency" },
  { value: "healthcare", label: "Healthcare" },
  { value: "finance", label: "Finance" },
  { value: "education", label: "Education" },
  { value: "realestate", label: "Real Estate" },
  { value: "other", label: "Other" },
];

const tonePills = ["Professional", "Friendly", "Bold", "Witty", "Inspirational", "Casual", "Authoritative", "Empathetic"];

// ── Helpers ─────────────────────────────────────────────────────────
function getPasswordStrength(pw: string) {
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { label: "Weak", color: "bg-red-500", pct: 20 };
  if (score <= 2) return { label: "Fair", color: "bg-amber-500", pct: 40 };
  if (score <= 3) return { label: "Good", color: "bg-yellow-500", pct: 60 };
  if (score <= 4) return { label: "Strong", color: "bg-emerald-500", pct: 80 };
  return { label: "Very Strong", color: "bg-emerald-400", pct: 100 };
}

function apiError(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
  );
}

async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post("/uploads/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return (res.data as { url: string }).url;
}

// ── Profile ─────────────────────────────────────────────────────────

function ProfileTab() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const [name, setName] = useState(user?.full_name ?? "");
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? "");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setName(user?.full_name ?? "");
    setAvatarUrl(user?.avatar_url ?? "");
  }, [user]);

  const initials =
    (name || user?.email || "U").split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

  const handleSave = async () => {
    if (!name.trim()) {
      showError("Name cannot be empty.");
      return;
    }
    setSaving(true);
    try {
      const updated: any = await put("/users/me", { full_name: name.trim() });
      setUser({ ...(user as any), ...updated });
      showSuccess("Profile updated.");
    } catch (err) {
      showError(apiError(err, "Could not save your profile."));
    } finally {
      setSaving(false);
    }
  };

  const handleAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const url = await uploadImage(file);
      const updated: any = await put("/users/me", { avatar_url: url });
      setAvatarUrl(url);
      setUser({ ...(user as any), ...updated });
      showSuccess("Profile photo updated.");
    } catch (err) {
      showError(apiError(err, "Could not upload your photo."));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Profile</h2>
        <p className="text-sm text-gray-400">Manage your personal information</p>
      </div>

      {/* Avatar */}
      <GlassCard>
        <div className="flex items-center gap-6">
          <div className="relative group cursor-pointer" onClick={() => fileRef.current?.click()}>
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-2xl font-bold text-white overflow-hidden">
              {avatarUrl ? (
                <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                initials
              )}
            </div>
            <div className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              {uploading ? (
                <Loader2 className="w-6 h-6 text-white animate-spin" />
              ) : (
                <Camera className="w-6 h-6 text-white" />
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatar}
            />
          </div>
          <div>
            <p className="text-white font-medium">{name || "User"}</p>
            <p className="text-sm text-gray-400">Click avatar to upload a new photo</p>
            <p className="text-xs text-gray-500 mt-1">JPG, PNG or GIF. Max 5MB.</p>
          </div>
        </div>
      </GlassCard>

      {/* Info */}
      <GlassCard>
        <div className="space-y-5">
          <Input label="Full Name" value={name} onChange={(e) => setName(e.target.value)} />
          <div className="relative">
            <Input label="Email" value={user?.email ?? ""} disabled />
            <Badge variant="info" className="absolute right-3 top-1/2 translate-y-1">Account</Badge>
          </div>
        </div>
      </GlassCard>

      <div className="flex justify-end">
        <Button variant="primary" loading={saving} onClick={handleSave}>
          Save Changes
        </Button>
      </div>
    </div>
  );
}

// ── Security ────────────────────────────────────────────────────────

interface SessionItem {
  id: string;
  device?: string;
  user_agent?: string;
  ip_address?: string;
  created_at: string;
  last_active_at: string;
  current: boolean;
}

function SecurityTab() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [changingPw, setChangingPw] = useState(false);

  // 2FA state
  const twoFaEnabled = !!user?.two_factor_enabled;
  const [setup, setSetup] = useState<{ secret: string; qr_code: string } | null>(null);
  const [enrollCode, setEnrollCode] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [startingSetup, setStartingSetup] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [showDisable2fa, setShowDisable2fa] = useState(false);
  const [disable2faPw, setDisable2faPw] = useState("");
  const [disabling2fa, setDisabling2fa] = useState(false);

  // Sessions
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);

  // Delete account
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);

  const strength = getPasswordStrength(newPw);

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data: any = await get("/users/me/sessions");
      setSessions(Array.isArray(data) ? data : data?.items ?? []);
    } catch {
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleChangePassword = async () => {
    if (newPw.length < 8) {
      showError("New password must be at least 8 characters.");
      return;
    }
    if (newPw !== confirmPw) {
      showError("Passwords do not match.");
      return;
    }
    setChangingPw(true);
    try {
      await post("/users/me/change-password", {
        current_password: currentPw,
        new_password: newPw,
      });
      showSuccess("Password updated.");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      showError(apiError(err, "Could not update your password."));
    } finally {
      setChangingPw(false);
    }
  };

  const handleStartSetup = async () => {
    setStartingSetup(true);
    try {
      const data: any = await post("/users/me/2fa/setup", {});
      setSetup({ secret: data.secret, qr_code: data.qr_code });
      setRecoveryCodes(null);
      setEnrollCode("");
    } catch (err) {
      showError(apiError(err, "Could not start 2FA setup."));
    } finally {
      setStartingSetup(false);
    }
  };

  const handleEnable = async () => {
    if (enrollCode.trim().length < 6) {
      showError("Enter the 6-digit code from your authenticator app.");
      return;
    }
    setEnrolling(true);
    try {
      const data: any = await post("/users/me/2fa/enable", { code: enrollCode.trim() });
      setRecoveryCodes(data.recovery_codes || []);
      setSetup(null);
      setEnrollCode("");
      setUser({ ...(user as any), two_factor_enabled: true });
      showSuccess("Two-factor authentication enabled.");
    } catch (err) {
      showError(apiError(err, "Invalid code. Please try again."));
    } finally {
      setEnrolling(false);
    }
  };

  const handleDisable2fa = async () => {
    if (!disable2faPw) return;
    setDisabling2fa(true);
    try {
      await post("/users/me/2fa/disable", { password: disable2faPw });
      setUser({ ...(user as any), two_factor_enabled: false });
      setShowDisable2fa(false);
      setDisable2faPw("");
      setRecoveryCodes(null);
      showSuccess("Two-factor authentication disabled.");
    } catch (err) {
      showError(apiError(err, "Could not disable 2FA."));
    } finally {
      setDisabling2fa(false);
    }
  };

  const handleRevokeSession = async (id: string) => {
    try {
      await del(`/users/me/sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      showSuccess("Session revoked.");
    } catch (err) {
      showError(apiError(err, "Could not revoke session."));
    }
  };

  const copyCodes = () => {
    if (recoveryCodes) {
      navigator.clipboard.writeText(recoveryCodes.join("\n"));
      showSuccess("Recovery codes copied.");
    }
  };

  const canDelete = deleteConfirm === "DELETE" && deletePassword.length > 0 && !deleting;
  const closeDeleteModal = () => {
    if (deleting) return;
    setShowDeleteModal(false);
    setDeleteConfirm("");
    setDeletePassword("");
  };

  const handleDeleteAccount = async () => {
    if (!canDelete) return;
    setDeleting(true);
    try {
      await del("/users/me", { data: { password: deletePassword } });
      showSuccess("Your account has been deleted.");
      logout();
      navigate("/", { replace: true });
    } catch (err) {
      showError(apiError(err, "Could not delete your account. Please try again."));
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Password & Security</h2>
        <p className="text-sm text-gray-400">Manage your account security settings</p>
      </div>

      {/* Change Password */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Change Password</h3>
        <div className="space-y-4 max-w-md">
          <Input label="Current Password" type={showPw ? "text" : "password"} value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} autoComplete="current-password" />
          <div>
            <Input label="New Password" type={showPw ? "text" : "password"} value={newPw} onChange={(e) => setNewPw(e.target.value)} autoComplete="new-password" />
            {newPw && (
              <div className="mt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">Password strength</span>
                  <span className={cn("text-xs font-medium", strength.pct >= 60 ? "text-emerald-400" : strength.pct >= 40 ? "text-amber-400" : "text-red-400")}>{strength.label}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${strength.pct}%` }} transition={{ duration: 0.3 }} className={cn("h-full rounded-full", strength.color)} />
                </div>
              </div>
            )}
          </div>
          <Input label="Confirm New Password" type={showPw ? "text" : "password"} value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} autoComplete="new-password" error={confirmPw && confirmPw !== newPw ? "Passwords do not match" : undefined} />
          <div className="flex items-center gap-3">
            <button onClick={() => setShowPw(!showPw)} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors">
              {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              {showPw ? "Hide" : "Show"} passwords
            </button>
          </div>
          <Button variant="primary" loading={changingPw} onClick={handleChangePassword} disabled={!currentPw || !newPw || !confirmPw}>
            Update Password
          </Button>
        </div>
      </GlassCard>

      {/* Two-Factor Authentication */}
      <GlassCard>
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              Two-Factor Authentication
              {twoFaEnabled && <Badge variant="success" size="sm">Enabled</Badge>}
            </h3>
            <p className="text-sm text-gray-400 mt-0.5">Add an extra layer of security to your account</p>
          </div>
          {twoFaEnabled ? (
            <Button variant="danger" size="sm" onClick={() => setShowDisable2fa(true)}>Disable</Button>
          ) : setup ? null : (
            <Button variant="secondary" size="sm" loading={startingSetup} onClick={handleStartSetup}>
              Set Up
            </Button>
          )}
        </div>

        {/* Setup flow */}
        <AnimatePresence>
          {setup && !twoFaEnabled && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-white/10 mt-4">
                <div>
                  <p className="text-sm text-gray-300 mb-3">1. Scan this QR code with your authenticator app (Google Authenticator, Authy, 1Password…)</p>
                  <div className="w-44 h-44 rounded-xl bg-white p-2 flex items-center justify-center">
                    <img src={setup.qr_code} alt="2FA QR code" className="w-full h-full" />
                  </div>
                  <p className="text-xs text-gray-500 mt-3">Or enter this key manually:</p>
                  <code className="text-xs text-purple-300 font-mono break-all">{setup.secret}</code>
                </div>
                <div>
                  <p className="text-sm text-gray-300 mb-3">2. Enter the 6-digit code from the app to finish</p>
                  <Input label="Verification code" value={enrollCode} onChange={(e) => setEnrollCode(e.target.value)} placeholder="123456" />
                  <div className="flex gap-2 mt-4">
                    <Button variant="primary" size="sm" loading={enrolling} onClick={handleEnable}>Enable 2FA</Button>
                    <Button variant="ghost" size="sm" onClick={() => { setSetup(null); setEnrollCode(""); }}>Cancel</Button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Recovery codes (shown once after enabling) */}
        {recoveryCodes && (
          <div className="pt-4 border-t border-white/10 mt-4">
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 mb-3">
              <p className="text-sm text-amber-300">Save these recovery codes somewhere safe. Each can be used once if you lose access to your authenticator. They won't be shown again.</p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {recoveryCodes.map((code) => (
                <div key={code} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 font-mono text-center">{code}</div>
              ))}
            </div>
            <Button variant="ghost" size="sm" icon={<Copy className="w-3.5 h-3.5" />} className="mt-3" onClick={copyCodes}>Copy All Codes</Button>
          </div>
        )}
      </GlassCard>

      {/* Active Sessions */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Active Sessions</h3>
        {loadingSessions ? (
          <div className="flex items-center justify-center py-6 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-6 text-sm text-gray-400">
            <p>No active sessions found.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-4 p-3 rounded-xl bg-white/5 border border-white/10">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                    <Monitor className="w-4 h-4 text-gray-300" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-white flex items-center gap-2">
                      {s.device || "Unknown device"}
                      {s.current && <Badge variant="success" size="sm">This device</Badge>}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {s.ip_address || "Unknown IP"} · Active {new Date(s.last_active_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                {!s.current && (
                  <button onClick={() => handleRevokeSession(s.id)} className="text-gray-400 hover:text-red-400 transition-colors flex-shrink-0" title="Revoke session">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Danger Zone */}
      <GlassCard className="!border-red-500/20">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-semibold text-red-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Danger Zone
            </h3>
            <p className="text-sm text-gray-400 mt-1">Permanently delete your account and all associated data. This action cannot be undone.</p>
          </div>
          <Button variant="danger" size="sm" onClick={() => setShowDeleteModal(true)}>Delete Account</Button>
        </div>
      </GlassCard>

      {/* Disable 2FA Modal */}
      <Modal isOpen={showDisable2fa} onClose={() => !disabling2fa && setShowDisable2fa(false)} title="Disable Two-Factor Authentication" size="sm">
        <div className="space-y-4">
          <p className="text-sm text-gray-400">Enter your password to turn off two-factor authentication.</p>
          <Input label="Password" type="password" value={disable2faPw} onChange={(e) => setDisable2faPw(e.target.value)} autoComplete="current-password" disabled={disabling2fa} />
          <div className="flex gap-3 justify-end">
            <Button variant="ghost" onClick={() => setShowDisable2fa(false)} disabled={disabling2fa}>Cancel</Button>
            <Button variant="danger" loading={disabling2fa} disabled={!disable2faPw} onClick={handleDisable2fa}>Disable</Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={showDeleteModal} onClose={closeDeleteModal} title="Delete Account" size="sm">
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <p className="text-sm text-red-300">This will permanently delete your account, all content, analytics, and team data. This cannot be undone.</p>
          </div>
          <Input label="Confirm your password" type="password" value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} disabled={deleting} autoComplete="current-password" />
          <Input label='Type "DELETE" to confirm' value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} disabled={deleting} />
          <div className="flex gap-3 justify-end">
            <Button variant="ghost" onClick={closeDeleteModal} disabled={deleting}>Cancel</Button>
            <Button variant="danger" disabled={!canDelete} loading={deleting} onClick={handleDeleteAccount}>
              {deleting ? "Deleting..." : "Delete Forever"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ── Notifications ───────────────────────────────────────────────────

function NotificationsTab() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const savedNotifs = user?.preferences?.notifications;
  const [emailNotifs, setEmailNotifs] = useState({ ...emailNotifDefaults, ...(savedNotifs?.email ?? {}) });
  const [inAppNotifs, setInAppNotifs] = useState({ ...inAppNotifDefaults, ...(savedNotifs?.inApp ?? {}) });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const n = user?.preferences?.notifications;
    if (n) {
      setEmailNotifs({ ...emailNotifDefaults, ...(n.email ?? {}) });
      setInAppNotifs({ ...inAppNotifDefaults, ...(n.inApp ?? {}) });
    }
  }, [user]);

  const notifItems: { key: keyof typeof emailNotifDefaults; label: string; desc: string }[] = [
    { key: "postPublished", label: "Post Published", desc: "When a scheduled post is successfully published" },
    { key: "postFailed", label: "Post Failed", desc: "When a post fails to publish" },
    { key: "weeklyReport", label: "Weekly Report", desc: "Weekly performance summary email" },
    { key: "strategyRecommendations", label: "Strategy Recommendations", desc: "AI-generated strategy suggestions" },
    { key: "teamInvitations", label: "Team Invitations", desc: "When you receive a team invitation" },
    { key: "billingAlerts", label: "Billing Alerts", desc: "Payment reminders and billing updates" },
  ];

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated: any = await put("/users/me", {
        preferences: { notifications: { email: emailNotifs, inApp: inAppNotifs } },
      });
      setUser({ ...(user as any), ...updated });
      showSuccess("Notification preferences saved.");
    } catch (err) {
      showError(apiError(err, "Could not save preferences."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Notifications</h2>
        <p className="text-sm text-gray-400">Choose how you want to be notified</p>
      </div>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Email Notifications</h3>
        <div className="space-y-4">
          {notifItems.map((item) => (
            <Toggle key={item.key} checked={emailNotifs[item.key]} onCheckedChange={(val) => setEmailNotifs((prev) => ({ ...prev, [item.key]: val }))} label={item.label} description={item.desc} />
          ))}
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">In-App Notifications</h3>
        <div className="space-y-4">
          {notifItems.map((item) => (
            <Toggle key={item.key} checked={inAppNotifs[item.key]} onCheckedChange={(val) => setInAppNotifs((prev) => ({ ...prev, [item.key]: val }))} label={item.label} description={item.desc} />
          ))}
        </div>
      </GlassCard>

      <div className="flex justify-end">
        <Button variant="primary" loading={saving} onClick={handleSave}>Save Preferences</Button>
      </div>
    </div>
  );
}

// ── Business Profile ────────────────────────────────────────────────

function BusinessProfileTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const logoRef = useRef<HTMLInputElement>(null);

  const [businessName, setBizName] = useState("");
  const [industry, setIndustry] = useState("saas");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [audience, setAudience] = useState("");
  const [selectedTones, setSelectedTones] = useState<string[]>([]);
  const [brandDesc, setBrandDesc] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const acc = await getAccountId();
        setAccountId(acc);
        if (!acc) return;
        const res: any = await get(`/accounts/${acc}/businesses/?per_page=1`);
        const biz = (res.items || res.data?.items || [])[0];
        if (biz) {
          setBusinessId(biz.id);
          setBizName(biz.name ?? "");
          setIndustry(biz.industry ?? "saas");
          setDescription(biz.description ?? "");
          setWebsite(biz.website ?? "");
          setLogoUrl(biz.logo_url ?? "");
          setAudience(biz.target_audience?.description ?? "");
          setSelectedTones(biz.brand_voice?.tones ?? []);
          setBrandDesc(biz.brand_voice?.description ?? "");
        }
      } catch {
        /* no business yet — that's fine */
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const toggleTone = (tone: string) => {
    setSelectedTones((prev) => (prev.includes(tone) ? prev.filter((t) => t !== tone) : [...prev, tone]));
  };

  const handleLogo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const url = await uploadImage(file);
      setLogoUrl(url);
      showSuccess("Logo uploaded. Remember to save.");
    } catch (err) {
      showError(apiError(err, "Could not upload logo."));
    } finally {
      setUploading(false);
      if (logoRef.current) logoRef.current.value = "";
    }
  };

  const handleSave = async () => {
    if (!accountId) {
      showError("No account found.");
      return;
    }
    if (!businessName.trim()) {
      showError("Business name is required.");
      return;
    }
    setSaving(true);
    const payload = {
      name: businessName.trim(),
      industry,
      description,
      website,
      logo_url: logoUrl || null,
      target_audience: { description: audience },
      brand_voice: { tones: selectedTones, description: brandDesc },
    };
    try {
      if (businessId) {
        await put(`/accounts/${accountId}/businesses/${businessId}`, payload);
      } else {
        // Create then patch the JSON fields the create endpoint doesn't accept.
        const created: any = await post(`/accounts/${accountId}/businesses/`, {
          name: payload.name,
          industry: payload.industry,
          description: payload.description,
          website: payload.website,
        });
        setBusinessId(created.id);
        await put(`/accounts/${accountId}/businesses/${created.id}`, payload);
      }
      showSuccess("Business profile saved.");
    } catch (err) {
      showError(apiError(err, "Could not save business profile."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Business Profile</h2>
        <p className="text-sm text-gray-400">Define your brand identity for AI-powered content generation</p>
      </div>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Basic Information</h3>
        <div className="space-y-5">
          <Input label="Business Name" value={businessName} onChange={(e) => setBizName(e.target.value)} />
          <Select label="Industry" options={industryOptions} value={industry} onChange={setIndustry} />
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none" />
          </div>
          <Input label="Website URL" value={website} onChange={(e) => setWebsite(e.target.value)} />
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Target Audience</h3>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Who is your ideal customer?</label>
          <textarea value={audience} onChange={(e) => setAudience(e.target.value)} rows={3} className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none" />
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Brand Voice</h3>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-3 pl-1">Tone (select all that apply)</label>
            <div className="flex flex-wrap gap-2">
              {tonePills.map((tone) => (
                <button key={tone} onClick={() => toggleTone(tone)} className={cn("px-4 py-1.5 rounded-full text-sm font-medium border transition-all duration-200", selectedTones.includes(tone) ? "bg-purple-500/20 border-purple-500/40 text-purple-300" : "bg-white/5 border-white/10 text-gray-400 hover:border-white/20 hover:text-gray-300")}>
                  {tone}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Brand Description</label>
            <textarea value={brandDesc} onChange={(e) => setBrandDesc(e.target.value)} rows={3} className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none" />
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Brand Logo</h3>
        <div className="flex items-center gap-5">
          <div onClick={() => logoRef.current?.click()} className="w-20 h-20 rounded-2xl bg-white/5 border-2 border-dashed border-white/10 flex items-center justify-center cursor-pointer hover:border-purple-500/30 transition-colors overflow-hidden">
            {uploading ? <Loader2 className="w-6 h-6 text-gray-400 animate-spin" /> : logoUrl ? <img src={logoUrl} alt="Logo" className="w-full h-full object-cover" /> : <Camera className="w-6 h-6 text-gray-500" />}
          </div>
          <input ref={logoRef} type="file" accept="image/*" className="hidden" onChange={handleLogo} />
          <div>
            <p className="text-sm text-gray-300">Upload your brand logo</p>
            <p className="text-xs text-gray-500 mt-1">SVG, PNG or JPG. Recommended 512x512px.</p>
          </div>
        </div>
      </GlassCard>

      <div className="flex justify-end">
        <Button variant="primary" loading={saving} onClick={handleSave}>Save Business Profile</Button>
      </div>
    </div>
  );
}

// ── Appearance ──────────────────────────────────────────────────────

function AppearanceTab() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const setSidebarCollapsed = useUIStore((s) => s.setSidebarCollapsed);

  const savedAppearance = user?.preferences?.appearance ?? {};
  const [sidebar, setSidebar] = useState<"expanded" | "collapsed">(
    sidebarCollapsed ? "collapsed" : (savedAppearance.sidebar ?? "expanded")
  );
  const [defaultView, setDefaultView] = useState(savedAppearance.defaultView ?? "overview");
  const [calendarView, setCalendarView] = useState<"week" | "month">(
    (localStorage.getItem("calendar_default_view") as "week" | "month") ||
    savedAppearance.calendarView ||
    "week"
  );

  useEffect(() => {
    if (savedAppearance.sidebar) {
      setSidebar(savedAppearance.sidebar);
      setSidebarCollapsed(savedAppearance.sidebar === "collapsed");
    }
    if (savedAppearance.defaultView) {
      setDefaultView(savedAppearance.defaultView);
    }
    if (savedAppearance.calendarView) {
      setCalendarView(savedAppearance.calendarView);
      localStorage.setItem("calendar_default_view", savedAppearance.calendarView);
    }
  }, [user]);

  const persist = useCallback(
    async (patch: Record<string, string>) => {
      try {
        const updated: any = await put("/users/me", { preferences: { appearance: patch } });
        setUser({ ...(user as any), ...updated });
        showSuccess("Appearance preference saved.");
      } catch (err) {
        showError(apiError(err, "Could not save preference."));
      }
    },
    [user, setUser]
  );

  const themeOptions = [
    { id: "dark" as const, icon: Moon, label: "Dark" },
    { id: "light" as const, icon: Sun, label: "Light" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Appearance</h2>
        <p className="text-sm text-gray-400">Customize the look and feel of your dashboard</p>
      </div>

      {/* Theme */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Theme</h3>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {themeOptions.map((opt) => {
            const active = theme === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => {
                  setTheme(opt.id);
                  persist({ theme: opt.id });
                }}
                className={cn(
                  "relative p-4 rounded-xl border-2 text-center transition-all",
                  active
                    ? "bg-purple-500/10 border-purple-500/50"
                    : "bg-white/5 border-white/10 hover:border-white/20"
                )}
              >
                <opt.icon className={cn("w-8 h-8 mx-auto mb-2", active ? "text-purple-400" : "text-gray-500")} />
                <p className={cn("text-sm font-medium", active ? "text-white" : "text-gray-400")}>{opt.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{active ? "Current theme" : "Click to switch"}</p>
                {active && (
                  <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                    <Check className="w-3 h-3 text-white" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </GlassCard>

      {/* Sidebar */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Sidebar Preference</h3>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {[
            { id: "expanded" as const, icon: PanelLeft, label: "Expanded" },
            { id: "collapsed" as const, icon: PanelLeftClose, label: "Collapsed" },
          ].map((opt) => (
            <button
              key={opt.id}
              onClick={() => {
                const isCollapsed = opt.id === "collapsed";
                setSidebar(opt.id);
                setSidebarCollapsed(isCollapsed);
                persist({ sidebar: opt.id });
              }}
              className={cn(
                "relative p-4 rounded-xl border-2 text-center transition-all",
                sidebar === opt.id
                  ? "bg-purple-500/10 border-purple-500/40"
                  : "bg-white/5 border-white/10 hover:border-white/20"
              )}
            >
              <opt.icon className={cn("w-8 h-8 mx-auto mb-2", sidebar === opt.id ? "text-purple-400" : "text-gray-500")} />
              <p className={cn("text-sm font-medium", sidebar === opt.id ? "text-white" : "text-gray-400")}>{opt.label}</p>
              {sidebar === opt.id && (
                <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" />
                </div>
              )}
            </button>
          ))}
        </div>
      </GlassCard>

      {/* Dashboard Default View */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Dashboard Default View</h3>
        <Select
          options={[
            { value: "overview", label: "Overview" },
            { value: "analytics", label: "Analytics" },
            { value: "content", label: "Content Calendar" },
            { value: "campaigns", label: "Campaigns" },
          ]}
          value={defaultView}
          onChange={(v) => {
            setDefaultView(v);
            persist({ defaultView: v });
          }}
          placeholder="Select default view"
          className="max-w-sm"
        />
      </GlassCard>

      {/* Calendar View */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Calendar Default View</h3>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {[
            { id: "week" as const, icon: CalendarDays, label: "Week View" },
            { id: "month" as const, icon: LayoutDashboard, label: "Month View" },
          ].map((opt) => (
            <button
              key={opt.id}
              onClick={() => {
                setCalendarView(opt.id);
                localStorage.setItem("calendar_default_view", opt.id);
                persist({ calendarView: opt.id });
              }}
              className={cn(
                "relative p-4 rounded-xl border-2 text-center transition-all",
                calendarView === opt.id
                  ? "bg-purple-500/10 border-purple-500/40"
                  : "bg-white/5 border-white/10 hover:border-white/20"
              )}
            >
              <opt.icon className={cn("w-8 h-8 mx-auto mb-2", calendarView === opt.id ? "text-purple-400" : "text-gray-500")} />
              <p className={cn("text-sm font-medium", calendarView === opt.id ? "text-white" : "text-gray-400")}>{opt.label}</p>
              {calendarView === opt.id && (
                <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" />
                </div>
              )}
            </button>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────

const tabComponents: Record<SettingsTab, JSX.Element> = {
  profile: <ProfileTab />,
  security: <SecurityTab />,
  notifications: <NotificationsTab />,
  business: <BusinessProfileTab />,
  appearance: <AppearanceTab />,
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const user = useAuthStore((s) => s.user);
  const loadUser = useAuthStore((s) => s.loadUser);

  // Ensure we have the freshest user (preferences, 2FA state) when landing here.
  useEffect(() => {
    if (!user) loadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <DashboardLayout>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="mb-8">
        <h1 className="text-3xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 mt-1">Manage your account and preferences</p>
      </motion.div>

      <div className="flex gap-8">
        {/* Sidebar Navigation */}
        <div className="w-64 flex-shrink-0">
          <GlassCard padding="sm">
            <nav className="space-y-1">
              {settingsNav.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button key={item.id} onClick={() => setActiveTab(item.id)} className={cn("w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200", isActive ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20" : "text-gray-400 hover:text-white hover:bg-white/5")}>
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </nav>
          </GlassCard>
        </div>

        {/* Content Area */}
        <div className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            <motion.div key={activeTab} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3 }}>
              {tabComponents[activeTab]}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </DashboardLayout>
  );
}
