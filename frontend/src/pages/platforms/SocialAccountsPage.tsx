import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  MoreHorizontal,
  Shield,
  RefreshCw,
  Trash2,
  Pencil,
  Globe,
  Key,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { cn, formatDate, formatNumber } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types & mock data                                                 */
/* ------------------------------------------------------------------ */

interface SocialAccount {
  id: string;
  platformName: string;
  platformColor: string;
  platformSlug: string;
  accountName: string;
  handle: string;
  profileUrl: string;
  isVerified: boolean;
  isActive: boolean;
  lastVerifiedAt: string | null;
  lastPostedAt: string | null;
  followers: number;
  following: number;
  createdAt: string;
  configFields: { key: string; label: string; value: string; type: string }[];
}

const mockAccounts: SocialAccount[] = [
  { id: "1", platformName: "Facebook", platformColor: "#1877F2", platformSlug: "facebook", accountName: "Acme Corp Facebook", handle: "@acmecorp", profileUrl: "https://facebook.com/acmecorp", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-30T10:00:00Z", lastPostedAt: "2026-03-29T14:00:00Z", followers: 15800, following: 320, createdAt: "2026-01-15T10:00:00Z", configFields: [{ key: "app_id", label: "App ID", value: "123456789", type: "text" }, { key: "page_id", label: "Page ID", value: "987654321", type: "text" }] },
  { id: "2", platformName: "Facebook", platformColor: "#1877F2", platformSlug: "facebook", accountName: "TechStartup Pro Page", handle: "@techstartuppro", profileUrl: "https://facebook.com/techstartuppro", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-30T10:00:00Z", lastPostedAt: "2026-03-28T09:00:00Z", followers: 4200, following: 180, createdAt: "2026-02-01T14:00:00Z", configFields: [] },
  { id: "3", platformName: "Instagram", platformColor: "#E4405F", platformSlug: "instagram", accountName: "Acme Corp Instagram", handle: "@acmecorp", profileUrl: "https://instagram.com/acmecorp", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-29T08:00:00Z", lastPostedAt: "2026-03-30T11:00:00Z", followers: 12400, following: 890, createdAt: "2026-01-15T10:00:00Z", configFields: [] },
  { id: "4", platformName: "Instagram", platformColor: "#E4405F", platformSlug: "instagram", accountName: "TechStartup Pro IG", handle: "@techstartuppro", profileUrl: "https://instagram.com/techstartuppro", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-28T15:00:00Z", lastPostedAt: "2026-03-27T16:00:00Z", followers: 3200, following: 450, createdAt: "2026-02-10T16:00:00Z", configFields: [] },
  { id: "5", platformName: "Instagram", platformColor: "#E4405F", platformSlug: "instagram", accountName: "Digital Spark Studio", handle: "@digispark", profileUrl: "https://instagram.com/digispark", isVerified: false, isActive: true, lastVerifiedAt: null, lastPostedAt: null, followers: 890, following: 230, createdAt: "2026-03-20T09:00:00Z", configFields: [] },
  { id: "6", platformName: "LinkedIn", platformColor: "#0A66C2", platformSlug: "linkedin", accountName: "Acme Corp LinkedIn", handle: "acme-corp", profileUrl: "https://linkedin.com/company/acme-corp", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-30T12:00:00Z", lastPostedAt: "2026-03-29T10:00:00Z", followers: 8700, following: 120, createdAt: "2026-01-20T14:00:00Z", configFields: [] },
  { id: "7", platformName: "LinkedIn", platformColor: "#0A66C2", platformSlug: "linkedin", accountName: "John Marketing Personal", handle: "johnmarketing", profileUrl: "https://linkedin.com/in/johnmarketing", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-30T12:00:00Z", lastPostedAt: "2026-03-28T08:00:00Z", followers: 2100, following: 650, createdAt: "2026-01-25T11:00:00Z", configFields: [] },
  { id: "8", platformName: "X (Twitter)", platformColor: "#000000", platformSlug: "twitter", accountName: "TechStartup Pro X", handle: "@techstartup", profileUrl: "https://x.com/techstartup", isVerified: true, isActive: true, lastVerifiedAt: "2026-03-29T14:00:00Z", lastPostedAt: "2026-03-30T09:00:00Z", followers: 5300, following: 980, createdAt: "2026-02-15T10:00:00Z", configFields: [] },
  { id: "9", platformName: "YouTube", platformColor: "#FF0000", platformSlug: "youtube", accountName: "TechStartup Pro Channel", handle: "@TechStartupPro", profileUrl: "https://youtube.com/@TechStartupPro", isVerified: false, isActive: true, lastVerifiedAt: null, lastPostedAt: null, followers: 1200, following: 45, createdAt: "2026-03-01T13:00:00Z", configFields: [] },
  { id: "10", platformName: "TikTok", platformColor: "#010101", platformSlug: "tiktok", accountName: "Digital Spark TikTok", handle: "@digispark", profileUrl: "https://tiktok.com/@digispark", isVerified: false, isActive: false, lastVerifiedAt: null, lastPostedAt: null, followers: 340, following: 120, createdAt: "2026-03-15T15:00:00Z", configFields: [] },
];

const platforms = [...new Set(mockAccounts.map((a) => a.platformName))];

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default function SocialAccountsPage() {
  const [accounts] = useState(mockAccounts);
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selectedAccount, setSelectedAccount] = useState<SocialAccount | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const filtered = accounts.filter((a) => {
    if (platformFilter !== "All" && a.platformName !== platformFilter) return false;
    if (statusFilter === "Verified" && !a.isVerified) return false;
    if (statusFilter === "Unverified" && a.isVerified) return false;
    if (statusFilter === "Inactive" && a.isActive) return false;
    if (search && !a.accountName.toLowerCase().includes(search.toLowerCase()) && !a.handle.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const verifiedCount = accounts.filter((a) => a.isVerified).length;

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Social Accounts</h1>
            <p className="mt-1 text-sm text-slate-400">
              {accounts.length} accounts across {platforms.length} platforms
              <span className="mx-2">·</span>
              <span className="text-green-400">{verifiedCount} verified</span>
            </p>
          </div>
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setShowAdd(true)}>
            Add Account
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search accounts..."
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2 pl-10 pr-4 text-sm text-white outline-none backdrop-blur-sm placeholder:text-slate-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20"
            />
          </div>
          <div className="flex gap-2 overflow-x-auto">
            {["All", ...platforms].map((p) => (
              <button
                key={p}
                onClick={() => setPlatformFilter(p)}
                className={cn(
                  "whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                  platformFilter === p
                    ? "bg-purple-500/20 text-purple-300 ring-1 ring-purple-500/30"
                    : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
                )}
              >
                {p}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {["All", "Verified", "Unverified", "Inactive"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                  statusFilter === s
                    ? "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30"
                    : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Accounts List */}
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map((account, i) => (
              <motion.div
                key={account.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ delay: i * 0.04 }}
              >
                <GlassCard padding="md" hover>
                  <div className="flex items-center gap-4">
                    {/* Platform indicator */}
                    <div
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white text-sm font-bold"
                      style={{ backgroundColor: account.platformColor + "20", color: account.platformColor }}
                    >
                      {account.platformName.charAt(0)}
                    </div>

                    {/* Account info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-white truncate">{account.accountName}</h3>
                        {account.isVerified ? (
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-green-400" />
                        ) : (
                          <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-slate-400">{account.handle}</span>
                        <span className="text-xs text-slate-600">·</span>
                        <Badge size="sm" variant="default">{account.platformName}</Badge>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="hidden sm:flex items-center gap-6 text-xs text-slate-400">
                      <div className="text-center">
                        <div className="font-semibold text-white">{formatNumber(account.followers)}</div>
                        <div>followers</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold text-white">{formatNumber(account.following)}</div>
                        <div>following</div>
                      </div>
                    </div>

                    {/* Status */}
                    <div className="hidden md:block">
                      {account.isVerified ? (
                        <Badge variant="success" size="sm" dot>Verified</Badge>
                      ) : account.isActive ? (
                        <Badge variant="warning" size="sm" dot>Unverified</Badge>
                      ) : (
                        <Badge variant="danger" size="sm" dot>Inactive</Badge>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setSelectedAccount(account)}
                        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                        title="View Details"
                      >
                        <Key className="h-4 w-4" />
                      </button>
                      <button
                        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-green-500/10 hover:text-green-400"
                        title="Test Connection"
                      >
                        <Shield className="h-4 w-4" />
                      </button>
                      <div className="relative">
                        <button
                          onClick={() => setMenuOpen(menuOpen === account.id ? null : account.id)}
                          className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                        <AnimatePresence>
                          {menuOpen === account.id && (
                            <motion.div
                              initial={{ opacity: 0, y: 5, scale: 0.95 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: 5, scale: 0.95 }}
                              className="absolute right-0 top-full z-20 mt-1 w-40 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 py-1 shadow-2xl backdrop-blur-xl"
                            >
                              <button className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                                <Pencil className="h-3.5 w-3.5" /> Edit
                              </button>
                              <button className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                                <RefreshCw className="h-3.5 w-3.5" /> Refresh Token
                              </button>
                              <button className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                                <Globe className="h-3.5 w-3.5" /> View Profile
                              </button>
                              <button className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10">
                                <Trash2 className="h-3.5 w-3.5" /> Delete
                              </button>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </div>
                  </div>

                  {/* Last activity row */}
                  <div className="mt-3 flex items-center gap-4 border-t border-white/5 pt-3 text-[11px] text-slate-500">
                    <span>Added {formatDate(account.createdAt)}</span>
                    {account.lastVerifiedAt && (
                      <>
                        <span>·</span>
                        <span>Verified {formatDate(account.lastVerifiedAt)}</span>
                      </>
                    )}
                    {account.lastPostedAt && (
                      <>
                        <span>·</span>
                        <span>Last post {formatDate(account.lastPostedAt)}</span>
                      </>
                    )}
                  </div>
                </GlassCard>
              </motion.div>
            ))}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div className="py-16 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5">
                <Search className="h-7 w-7 text-slate-500" />
              </div>
              <h3 className="text-lg font-semibold text-white">No accounts found</h3>
              <p className="mt-1 text-sm text-slate-400">Try adjusting your filters or add a new account.</p>
            </div>
          )}
        </div>
      </div>

      {/* Account Detail Modal */}
      <Modal isOpen={!!selectedAccount} onClose={() => setSelectedAccount(null)} title="Account Details" size="md">
        {selectedAccount && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold"
                style={{ backgroundColor: selectedAccount.platformColor + "20", color: selectedAccount.platformColor }}
              >
                {selectedAccount.platformName.charAt(0)}
              </div>
              <div>
                <h3 className="font-semibold text-white">{selectedAccount.accountName}</h3>
                <p className="text-sm text-slate-400">{selectedAccount.handle} · {selectedAccount.platformName}</p>
              </div>
              {selectedAccount.isVerified ? (
                <Badge variant="success" size="sm" dot>Verified</Badge>
              ) : (
                <Badge variant="warning" size="sm" dot>Unverified</Badge>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-white/5 p-3">
                <div className="text-lg font-bold text-white">{formatNumber(selectedAccount.followers)}</div>
                <div className="text-xs text-slate-400">Followers</div>
              </div>
              <div className="rounded-xl bg-white/5 p-3">
                <div className="text-lg font-bold text-white">{formatNumber(selectedAccount.following)}</div>
                <div className="text-xs text-slate-400">Following</div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-medium uppercase tracking-wider text-slate-500">Connection Details</h4>
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Profile URL</span><a href={selectedAccount.profileUrl} className="text-purple-400 hover:underline">{selectedAccount.profileUrl}</a></div>
                <div className="flex justify-between"><span className="text-slate-400">Status</span><span className={selectedAccount.isVerified ? "text-green-400" : "text-amber-400"}>{selectedAccount.isVerified ? "Verified" : "Unverified"}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Last Verified</span><span className="text-white">{selectedAccount.lastVerifiedAt ? formatDate(selectedAccount.lastVerifiedAt) : "Never"}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Last Posted</span><span className="text-white">{selectedAccount.lastPostedAt ? formatDate(selectedAccount.lastPostedAt) : "Never"}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">API Key</span><span className="font-mono text-xs text-slate-300">••••••••{selectedAccount.id.slice(-4)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Access Token</span><span className="font-mono text-xs text-slate-300">••••••••••••</span></div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="secondary" size="sm" icon={<Shield className="h-4 w-4" />}>Test Connection</Button>
              <Button variant="secondary" size="sm" icon={<RefreshCw className="h-4 w-4" />}>Refresh Token</Button>
              <Button variant="ghost" size="sm" icon={<Pencil className="h-4 w-4" />}>Edit</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Add Account Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add Social Account" size="md">
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Platform</label>
            <select className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-purple-500/50">
              <option value="">Select a platform...</option>
              {platforms.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <Input label="Account Name" placeholder="e.g., My Client's Instagram" />
          <Input label="Handle / Username" placeholder="e.g., @mycompany" />
          <Input label="Profile URL" placeholder="https://..." />
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <h4 className="mb-3 text-sm font-medium text-white flex items-center gap-2">
              <Key className="h-4 w-4 text-purple-400" /> API Credentials
            </h4>
            <div className="space-y-3">
              <Input label="API Key" placeholder="Your API key" />
              <Input label="API Secret" type="password" placeholder="Your API secret" />
              <Input label="Access Token" type="password" placeholder="OAuth access token" />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowAdd(false)}>Cancel</Button>
            <Button icon={<Plus className="h-4 w-4" />}>Add Account</Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
