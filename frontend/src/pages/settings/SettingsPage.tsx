import { useState, type JSX } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  User,
  Lock,
  Bell,
  Building2,
  Palette,
  Camera,
  Shield,
  Monitor,
  Smartphone,
  QrCode,
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

// ── Password strength helper ────────────────────────────────────────
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

// ── Sub-page Components ─────────────────────────────────────────────

function ProfileTab() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [saved, setSaved] = useState(false);

  const initials = name.split(" ").map((n) => n[0]).join("").toUpperCase();

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Profile</h2>
        <p className="text-sm text-gray-400">Manage your personal information</p>
      </div>

      {/* Avatar */}
      <GlassCard>
        <div className="flex items-center gap-6">
          <div className="relative group cursor-pointer">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-2xl font-bold text-white">
              {initials}
            </div>
            <div className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <Camera className="w-6 h-6 text-white" />
            </div>
          </div>
          <div>
            <p className="text-white font-medium">{name || "User"}</p>
            <p className="text-sm text-gray-400">Click avatar to upload a new photo</p>
            <p className="text-xs text-gray-500 mt-1">JPG, PNG or GIF. Max 2MB.</p>
          </div>
        </div>
      </GlassCard>

      {/* Info */}
      <GlassCard>
        <div className="space-y-5">
          <Input label="Full Name" value={name} onChange={(e) => { setName(e.target.value); setSaved(false); }} />
          <div className="relative">
            <Input label="Email" value={email} disabled />
            <Badge variant="info" className="absolute right-3 top-1/2 -translate-y-1/2">Verified</Badge>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Role</label>
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10">
              <Shield className="w-4 h-4 text-purple-400" />
              <span className="text-sm text-white">{role || "Member"}</span>
            </div>
          </div>
        </div>
      </GlassCard>

      <div className="flex justify-end">
        <Button variant="primary" icon={saved ? <Check className="w-4 h-4" /> : undefined} onClick={() => setSaved(true)}>
          {saved ? "Saved!" : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}

function SecurityTab() {
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [twoFa, setTwoFa] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  const strength = getPasswordStrength(newPw);

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
          <Input label="Current Password" type={showPw ? "text" : "password"} value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} />
          <div>
            <Input label="New Password" type={showPw ? "text" : "password"} value={newPw} onChange={(e) => setNewPw(e.target.value)} />
            {newPw && (
              <div className="mt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">Password strength</span>
                  <span className={cn("text-xs font-medium", strength.pct >= 60 ? "text-emerald-400" : strength.pct >= 40 ? "text-amber-400" : "text-red-400")}>{strength.label}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${strength.pct}%` }}
                    transition={{ duration: 0.3 }}
                    className={cn("h-full rounded-full", strength.color)}
                  />
                </div>
              </div>
            )}
          </div>
          <Input label="Confirm New Password" type={showPw ? "text" : "password"} value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} error={confirmPw && confirmPw !== newPw ? "Passwords do not match" : undefined} />
          <div className="flex items-center gap-3">
            <button onClick={() => setShowPw(!showPw)} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors">
              {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              {showPw ? "Hide" : "Show"} passwords
            </button>
          </div>
          <Button variant="primary">Update Password</Button>
        </div>
      </GlassCard>

      {/* Two-Factor Authentication */}
      <GlassCard>
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="text-base font-semibold text-white">Two-Factor Authentication</h3>
            <p className="text-sm text-gray-400 mt-0.5">Add an extra layer of security to your account</p>
          </div>
          <Toggle checked={twoFa} onCheckedChange={setTwoFa} />
        </div>

        <AnimatePresence>
          {twoFa && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-white/10">
                {/* QR Code */}
                <div>
                  <p className="text-sm text-gray-300 mb-3">Scan this QR code with your authenticator app</p>
                  <div className="w-40 h-40 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center">
                    <QrCode className="w-20 h-20 text-gray-500" />
                  </div>
                </div>
                {/* Recovery Codes */}
                <div>
                  <p className="text-sm text-gray-300 mb-3">Recovery Codes</p>
                  <div className="grid grid-cols-2 gap-2">
                    {["A4K9-M2X7", "B8L3-N5Y1", "C2P6-Q9Z4", "D7R1-S3W8", "E5T4-U6V2", "F1X8-G3H9"].map((code) => (
                      <div key={code} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 font-mono text-center">{code}</div>
                    ))}
                  </div>
                  <Button variant="ghost" size="sm" icon={<Copy className="w-3.5 h-3.5" />} className="mt-3">Copy All Codes</Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>

      {/* Active Sessions */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Active Sessions</h3>
        <div className="text-center py-6 text-sm text-gray-400">
          <p>No active sessions found. Sign in on a device to see it here.</p>
        </div>
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

      {/* Delete Confirmation Modal */}
      <Modal isOpen={showDeleteModal} onClose={() => { setShowDeleteModal(false); setDeleteConfirm(""); }} title="Delete Account" size="sm">
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <p className="text-sm text-red-300">This will permanently delete your account, all content, analytics, and team data. This cannot be undone.</p>
          </div>
          <Input label='Type "DELETE" to confirm' value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} />
          <div className="flex gap-3 justify-end">
            <Button variant="ghost" onClick={() => { setShowDeleteModal(false); setDeleteConfirm(""); }}>Cancel</Button>
            <Button variant="danger" disabled={deleteConfirm !== "DELETE"}>Delete Forever</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function NotificationsTab() {
  const [emailNotifs, setEmailNotifs] = useState(emailNotifDefaults);
  const [inAppNotifs, setInAppNotifs] = useState(inAppNotifDefaults);
  const [pushEnabled, setPushEnabled] = useState(false);

  const notifItems: { key: keyof typeof emailNotifDefaults; label: string; desc: string }[] = [
    { key: "postPublished", label: "Post Published", desc: "When a scheduled post is successfully published" },
    { key: "postFailed", label: "Post Failed", desc: "When a post fails to publish" },
    { key: "weeklyReport", label: "Weekly Report", desc: "Weekly performance summary email" },
    { key: "strategyRecommendations", label: "Strategy Recommendations", desc: "AI-generated strategy suggestions" },
    { key: "teamInvitations", label: "Team Invitations", desc: "When you receive a team invitation" },
    { key: "billingAlerts", label: "Billing Alerts", desc: "Payment reminders and billing updates" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Notifications</h2>
        <p className="text-sm text-gray-400">Choose how you want to be notified</p>
      </div>

      {/* Email Notifications */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Email Notifications</h3>
        <div className="space-y-4">
          {notifItems.map((item) => (
            <Toggle
              key={item.key}
              checked={emailNotifs[item.key]}
              onCheckedChange={(val) => setEmailNotifs((prev) => ({ ...prev, [item.key]: val }))}
              label={item.label}
              description={item.desc}
            />
          ))}
        </div>
      </GlassCard>

      {/* In-App Notifications */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">In-App Notifications</h3>
        <div className="space-y-4">
          {notifItems.map((item) => (
            <Toggle
              key={item.key}
              checked={inAppNotifs[item.key]}
              onCheckedChange={(val) => setInAppNotifs((prev) => ({ ...prev, [item.key]: val }))}
              label={item.label}
              description={item.desc}
            />
          ))}
        </div>
      </GlassCard>

      {/* Push Notifications */}
      <GlassCard>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                Push Notifications
                <Badge variant="default" size="sm">Coming Soon</Badge>
              </h3>
              <p className="text-sm text-gray-400 mt-0.5">Receive push notifications on your devices</p>
            </div>
          </div>
          <Toggle checked={pushEnabled} onCheckedChange={setPushEnabled} disabled />
        </div>
      </GlassCard>
    </div>
  );
}

function BusinessProfileTab() {
  const [businessName, setBizName] = useState("Visionary Space");
  const [industry, setIndustry] = useState("saas");
  const [description, setDescription] = useState("AI-powered marketing automation platform helping businesses scale their social media presence.");
  const [website, setWebsite] = useState("https://visionaryspace.io");
  const [audience, setAudience] = useState("SaaS founders, marketing managers, small business owners, content creators");
  const [selectedTones, setSelectedTones] = useState<string[]>(["Professional", "Bold", "Witty"]);
  const [brandDesc, setBrandDesc] = useState("We are a forward-thinking technology company that empowers marketers with AI-driven insights and automation tools.");

  const toggleTone = (tone: string) => {
    setSelectedTones((prev) => prev.includes(tone) ? prev.filter((t) => t !== tone) : [...prev, tone]);
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">Business Profile</h2>
        <p className="text-sm text-gray-400">Define your brand identity for AI-powered content generation</p>
      </div>

      {/* Basic Info */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Basic Information</h3>
        <div className="space-y-5">
          <Input label="Business Name" value={businessName} onChange={(e) => setBizName(e.target.value)} />
          <Select label="Industry" options={industryOptions} value={industry} onChange={setIndustry} />
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
            />
          </div>
          <Input label="Website URL" value={website} onChange={(e) => setWebsite(e.target.value)} />
        </div>
      </GlassCard>

      {/* Target Audience */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Target Audience</h3>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Who is your ideal customer?</label>
          <textarea
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            rows={3}
            className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
          />
        </div>
      </GlassCard>

      {/* Brand Voice */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Brand Voice</h3>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-3 pl-1">Tone (select all that apply)</label>
            <div className="flex flex-wrap gap-2">
              {tonePills.map((tone) => (
                <button
                  key={tone}
                  onClick={() => toggleTone(tone)}
                  className={cn(
                    "px-4 py-1.5 rounded-full text-sm font-medium border transition-all duration-200",
                    selectedTones.includes(tone)
                      ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                      : "bg-white/5 border-white/10 text-gray-400 hover:border-white/20 hover:text-gray-300"
                  )}
                >
                  {tone}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">Brand Description</label>
            <textarea
              value={brandDesc}
              onChange={(e) => setBrandDesc(e.target.value)}
              rows={3}
              className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
            />
          </div>
        </div>
      </GlassCard>

      {/* Logo */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Brand Logo</h3>
        <div className="flex items-center gap-5">
          <div className="w-20 h-20 rounded-2xl bg-white/5 border-2 border-dashed border-white/10 flex items-center justify-center cursor-pointer hover:border-purple-500/30 transition-colors">
            <Camera className="w-6 h-6 text-gray-500" />
          </div>
          <div>
            <p className="text-sm text-gray-300">Upload your brand logo</p>
            <p className="text-xs text-gray-500 mt-1">SVG, PNG or JPG. Recommended 512x512px.</p>
          </div>
        </div>
      </GlassCard>

      <div className="flex justify-end">
        <Button variant="primary">Save Business Profile</Button>
      </div>
    </div>
  );
}

function AppearanceTab() {
  const [sidebar, setSidebar] = useState<"expanded" | "collapsed">("expanded");
  const [defaultView, setDefaultView] = useState("overview");
  const [calendarView, setCalendarView] = useState("week");

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
          <button className="relative p-4 rounded-xl bg-slate-900 border-2 border-purple-500/50 text-center transition-all">
            <Moon className="w-8 h-8 text-purple-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-white">Dark</p>
            <p className="text-xs text-gray-400 mt-0.5">Current theme</p>
            <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
              <Check className="w-3 h-3 text-white" />
            </div>
          </button>
          <button className="relative p-4 rounded-xl bg-white/5 border-2 border-white/10 text-center opacity-50 cursor-not-allowed">
            <Sun className="w-8 h-8 text-gray-500 mx-auto mb-2" />
            <p className="text-sm font-medium text-gray-400">Light</p>
            <Badge variant="default" size="sm" className="mt-1">Coming Soon</Badge>
          </button>
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
              onClick={() => setSidebar(opt.id)}
              className={cn(
                "relative p-4 rounded-xl border-2 text-center transition-all",
                sidebar === opt.id ? "bg-purple-500/10 border-purple-500/40" : "bg-white/5 border-white/10 hover:border-white/20"
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
          onChange={setDefaultView}
          placeholder="Select default view"
          className="max-w-sm"
        />
      </GlassCard>

      {/* Calendar View */}
      <GlassCard>
        <h3 className="text-base font-semibold text-white mb-5">Calendar Default View</h3>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {[
            { id: "week", icon: CalendarDays, label: "Week View" },
            { id: "month", icon: LayoutDashboard, label: "Month View" },
          ].map((opt) => (
            <button
              key={opt.id}
              onClick={() => setCalendarView(opt.id)}
              className={cn(
                "relative p-4 rounded-xl border-2 text-center transition-all",
                calendarView === opt.id ? "bg-purple-500/10 border-purple-500/40" : "bg-white/5 border-white/10 hover:border-white/20"
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
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                      isActive
                        ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20"
                        : "text-gray-400 hover:text-white hover:bg-white/5"
                    )}
                  >
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
