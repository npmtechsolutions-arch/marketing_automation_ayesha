import { useState, useEffect, useMemo } from "react";
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
import api, { getAccountId } from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";

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
  profileImageUrl?: string;
  isVerified: boolean;
  isActive: boolean;
  lastVerifiedAt: string | null;
  lastPostedAt: string | null;
  followers: number;
  following: number;
  createdAt: string;
  configFields: { key: string; label: string; value: string; type: string }[];
  platformId: string;
}

const getProxiedImageUrl = (url?: string) => {
  if (!url) return "";
  if (url.includes("fbcdn.net") || url.includes("cdninstagram.com") || url.includes("instagram.com")) {
    const accountId = localStorage.getItem("account_id");
    if (accountId) {
      return `/api/v1/accounts/${accountId}/social-accounts/proxy-image?url=${encodeURIComponent(url)}`;
    }
  }
  return url;
};

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default function SocialAccountsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [dbPlatforms, setDbPlatforms] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selectedAccount, setSelectedAccount] = useState<SocialAccount | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  // Form Mode State
  const [isEdit, setIsEdit] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);

  // Form State
  const [formPlatformId, setFormPlatformId] = useState("");
  const [formAccountName, setFormAccountName] = useState("");
  const [formHandle, setFormHandle] = useState("");
  const [formProfileUrl, setFormProfileUrl] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formApiSecret, setFormApiSecret] = useState("");
  const [formAccessToken, setFormAccessToken] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const accountId = localStorage.getItem("account_id");

  const fetchAccountsAndPlatforms = async () => {
    let activeAccountId = localStorage.getItem("account_id");
    if (!activeAccountId) {
      try {
        const accRes: any = await api.get("/accounts");
        const items = accRes.items || accRes.data?.items || (Array.isArray(accRes) ? accRes : []);
        if (items.length > 0 && items[0].id) {
          activeAccountId = items[0].id;
          localStorage.setItem("account_id", activeAccountId);
        }
      } catch (err) {
        console.warn("Could not auto-resolve account_id:", err);
      }
    }

    if (!activeAccountId) return;

    try {
      // Fetch platforms
      const platformsRes: any = await api.get(`/accounts/${activeAccountId}/social-platforms/`);
      const fetchedPlatforms = platformsRes.items || platformsRes.data?.items || [];
      setDbPlatforms(fetchedPlatforms);

      // Fetch accounts
      const accountsRes: any = await api.get(`/accounts/${activeAccountId}/social-accounts/`);
      const fetchedAccounts = accountsRes.items || accountsRes.data?.items || [];
      
      const mappedAccounts = fetchedAccounts.map((item: any) => ({
        id: item.id,
        platformName: item.platform?.name || "Unknown",
        platformColor: item.platform?.color || "#6366F1",
        platformSlug: item.platform?.slug || "unknown",
        accountName: item.account_name,
        handle: item.account_handle || "",
        profileUrl: item.profile_url || "",
        profileImageUrl: item.profile_image_url || "",
        isVerified: item.is_verified,
        isActive: item.is_active,
        lastVerifiedAt: item.last_verified_at,
        lastPostedAt: item.last_posted_at,
        followers: item.metadata?.followers || 0,
        following: item.metadata?.following || 0,
        createdAt: item.created_at,
        configFields: [],
        platformId: item.platform_id || "",
      }));
      
      setAccounts(mappedAccounts);
    } catch (err) {
      console.error("Failed to fetch accounts/platforms:", err);
    }
  };

  useEffect(() => {
    fetchAccountsAndPlatforms();

    // Check URL params for OAuth return status
    const params = new URLSearchParams(window.location.search);
    const fbResult = params.get("facebook");
    const igResult = params.get("instagram");
    const liResult = params.get("linkedin");
    const twitterResult = params.get("twitter");
    const youtubeResult = params.get("youtube");
    const reason = params.get("reason");

    if (fbResult === "success") {
      showSuccess("Facebook Page connected successfully!");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    } else if (fbResult === "error") {
      showError(reason || "Failed to connect Facebook Page.");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    }

    if (igResult === "success") {
      showSuccess("Instagram Business Account connected successfully!");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    } else if (igResult === "error") {
      showError(reason || "Failed to connect Instagram Business Account.");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    }

    if (liResult === "success") {
      showSuccess("LinkedIn Account connected successfully!");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    } else if (liResult === "error") {
      showError(reason || "Failed to connect LinkedIn Account.");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    }

    if (twitterResult === "success") {
      showSuccess("X (Twitter) Account connected successfully!");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    } else if (twitterResult === "error") {
      showError(reason || "Failed to connect X (Twitter) Account.");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    }

    if (youtubeResult === "success") {
      showSuccess("YouTube Channel connected successfully!");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    } else if (youtubeResult === "error") {
      showError(reason || "Failed to connect YouTube Channel.");
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
    }
  }, []);

  // Close dropdown menu when clicking outside of it
  useEffect(() => {
    if (!menuOpen) return;
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".relative")) {
        setMenuOpen(null);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [menuOpen]);

  const handleAddAccount = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId || !formPlatformId || !formAccountName) return;
    setIsLoading(true);
    try {
      await api.post(`/accounts/${activeAccountId}/social-accounts/`, {
        platform_id: formPlatformId,
        account_name: formAccountName,
        account_handle: formHandle,
        profile_url: formProfileUrl,
        api_key: formApiKey,
        api_secret: formApiSecret,
        access_token: formAccessToken,
        config: {}
      });
      // Reset form and refresh
      setFormPlatformId("");
      setFormAccountName("");
      setFormHandle("");
      setFormProfileUrl("");
      setFormApiKey("");
      setFormApiSecret("");
      setFormAccessToken("");
      setShowAdd(false);
      await fetchAccountsAndPlatforms();
    } catch (error) {
      console.error("Error adding account:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteAccount = async (id: string) => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    if (confirm("Are you sure you want to delete this account?")) {
      try {
        await api.delete(`/accounts/${activeAccountId}/social-accounts/${id}`);
        setMenuOpen(null);
        await fetchAccountsAndPlatforms();
      } catch (error) {
        console.error("Error deleting account:", error);
      }
    }
  };

  const handleVerifyAccount = async (id: string) => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      await api.post(`/accounts/${activeAccountId}/social-accounts/${id}/verify`);
      showSuccess("Social account connection verified successfully!");
      await fetchAccountsAndPlatforms();
      if (selectedAccount && selectedAccount.id === id) {
        setSelectedAccount((prev) =>
          prev
            ? {
                ...prev,
                isVerified: true,
                lastVerifiedAt: new Date().toISOString(),
              }
            : null
        );
      }
    } catch (error) {
      console.error("Error verifying account:", error);
      showError("Failed to verify social account connection.");
    }
  };

  const handleEditClick = (account: SocialAccount) => {
    setIsEdit(true);
    setEditId(account.id);
    setFormPlatformId(account.platformId);
    setFormAccountName(account.accountName);
    setFormHandle(account.handle);
    setFormProfileUrl(account.profileUrl);
    setFormApiKey("");
    setFormApiSecret("");
    setFormAccessToken("");
    setShowAdd(true);
    setMenuOpen(null);
    setSelectedAccount(null);
  };

  const handleUpdateAccount = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId || !editId || !formAccountName) return;
    setIsLoading(true);
    try {
      const payload: any = {
        account_name: formAccountName,
        account_handle: formHandle,
        profile_url: formProfileUrl,
      };
      if (formApiKey) payload.api_key = formApiKey;
      if (formApiSecret) payload.api_secret = formApiSecret;
      if (formAccessToken) payload.access_token = formAccessToken;

      await api.put(`/accounts/${activeAccountId}/social-accounts/${editId}`, payload);
      showSuccess("Social account updated successfully!");
      
      // Reset form and refresh
      setFormPlatformId("");
      setFormAccountName("");
      setFormHandle("");
      setFormProfileUrl("");
      setFormApiKey("");
      setFormApiSecret("");
      setFormAccessToken("");
      setIsEdit(false);
      setEditId(null);
      setShowAdd(false);
      await fetchAccountsAndPlatforms();
    } catch (error) {
      console.error("Error updating account:", error);
      showError("Failed to update social account.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshToken = async (id: string) => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      await api.post(`/accounts/${activeAccountId}/social-accounts/${id}/refresh-token`);
      showSuccess("Token refresh initiated successfully!");
      setMenuOpen(null);
      await fetchAccountsAndPlatforms();
    } catch (error: any) {
      console.error("Error refreshing token:", error);
      const errMsg = error.response?.data?.detail || "Failed to refresh token.";
      showError(errMsg);
    }
  };

  const handleFacebookOAuth = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    const fbPlatform = dbPlatforms.find((p) => (p.slug || "").toLowerCase() === "facebook");
    if (!fbPlatform) {
      showError("Facebook platform is not configured in this workspace.");
      return;
    }
    try {
      setIsLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/facebook/authorize?platform_id=${fbPlatform.id}`);
      const authUrl = res.auth_url || res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        showError("Failed to generate Facebook authorization URL.");
      }
    } catch (err: any) {
      console.error("Facebook OAuth initiation error:", err);
      showError(err.response?.data?.detail || "Failed to initiate Facebook OAuth.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleInstagramOAuth = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    const igPlatform = dbPlatforms.find((p) => (p.slug || "").toLowerCase() === "instagram");
    if (!igPlatform) {
      showError("Instagram platform is not configured in this workspace.");
      return;
    }
    try {
      setIsLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/instagram/authorize?platform_id=${igPlatform.id}`);
      const authUrl = res.auth_url || res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        showError("Failed to generate Instagram authorization URL.");
      }
    } catch (err: any) {
      console.error("Instagram OAuth initiation error:", err);
      showError(err.response?.data?.detail || "Failed to initiate Instagram OAuth.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLinkedinOAuth = async (target: "personal" | "organization") => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    const liPlatform = dbPlatforms.find((p) => (p.slug || "").toLowerCase() === "linkedin");
    if (!liPlatform) {
      showError("LinkedIn platform is not configured in this workspace.");
      return;
    }
    try {
      setIsLoading(true);
      const res: any = await api.get(
        `/accounts/${activeAccountId}/linkedin/authorize?platform_id=${liPlatform.id}&target=${target}`
      );
      const authUrl = res.auth_url || res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        showError("Failed to generate LinkedIn authorization URL.");
      }
    } catch (err: any) {
      console.error("LinkedIn OAuth initiation error:", err);
      showError(err.response?.data?.detail || "Failed to initiate LinkedIn OAuth.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTwitterOAuth = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    const twPlatform = dbPlatforms.find((p) =>
      ["twitter", "x"].includes((p.slug || "").toLowerCase())
    );
    if (!twPlatform) {
      showError("X (Twitter) platform is not configured in this workspace.");
      return;
    }
    try {
      setIsLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/twitter/authorize?platform_id=${twPlatform.id}`);
      const authUrl = res.auth_url || res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        showError("Failed to generate X authorization URL.");
      }
    } catch (err: any) {
      console.error("X OAuth initiation error:", err);
      showError(err.response?.data?.detail || "Failed to initiate X OAuth.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleYoutubeOAuth = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    const ytPlatform = dbPlatforms.find((p) => (p.slug || "").toLowerCase() === "youtube");
    if (!ytPlatform) {
      showError("YouTube platform is not configured in this workspace.");
      return;
    }
    try {
      setIsLoading(true);
      const res: any = await api.get(`/accounts/${activeAccountId}/youtube/authorize?platform_id=${ytPlatform.id}`);
      const authUrl = res.auth_url || res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        showError("Failed to generate YouTube authorization URL.");
      }
    } catch (err: any) {
      console.error("YouTube OAuth initiation error:", err);
      showError(err.response?.data?.detail || "Failed to initiate YouTube OAuth.");
    } finally {
      setIsLoading(false);
    }
  };

  const platforms = useMemo(() => {
    return [...new Set(accounts.map((a) => a.platformName))];
  }, [accounts]);

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
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => { setIsEdit(false); setEditId(null); setShowAdd(true); }}>
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
                    {/* Platform indicator / Profile Image */}
                    <div className="relative shrink-0">
                      {account.profileImageUrl ? (
                        <img
                          src={getProxiedImageUrl(account.profileImageUrl)}
                          alt={account.accountName}
                          className="h-11 w-11 rounded-xl object-cover ring-2 ring-white/10"
                          onError={(e) => {
                            e.currentTarget.src = "";
                            e.currentTarget.className = "hidden";
                            const fallback = e.currentTarget.nextElementSibling;
                            if (fallback) fallback.classList.remove("hidden");
                          }}
                        />
                      ) : null}
                      <div
                        className={cn(
                          "flex h-11 w-11 items-center justify-center rounded-xl text-white text-sm font-bold",
                          account.profileImageUrl ? "hidden" : ""
                        )}
                        style={{ backgroundColor: account.platformColor + "20", color: account.platformColor }}
                      >
                        {account.platformName.charAt(0)}
                      </div>
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
                        onClick={() => handleVerifyAccount(account.id)}
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
                              <button 
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleEditClick(account);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
                              >
                                <Pencil className="h-3.5 w-3.5" /> Edit
                              </button>
                              <button 
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRefreshToken(account.id);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
                              >
                                <RefreshCw className="h-3.5 w-3.5" /> Refresh Token
                              </button>
                              <button 
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (account.profileUrl) {
                                    window.open(account.profileUrl, "_blank", "noopener,noreferrer");
                                  } else {
                                    showError("Profile URL not available.");
                                  }
                                  setMenuOpen(null);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
                              >
                                <Globe className="h-3.5 w-3.5" /> View Profile
                              </button>
                              <button 
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteAccount(account.id);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10"
                              >
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
              <div className="relative shrink-0">
                {selectedAccount.profileImageUrl ? (
                  <img
                    src={getProxiedImageUrl(selectedAccount.profileImageUrl)}
                    alt={selectedAccount.accountName}
                    className="h-12 w-12 rounded-xl object-cover ring-2 ring-white/10"
                    onError={(e) => {
                      e.currentTarget.src = "";
                      e.currentTarget.className = "hidden";
                      const fallback = e.currentTarget.nextElementSibling;
                      if (fallback) fallback.classList.remove("hidden");
                    }}
                  />
                ) : null}
                <div
                  className={cn(
                    "flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold",
                    selectedAccount.profileImageUrl ? "hidden" : ""
                  )}
                  style={{ backgroundColor: selectedAccount.platformColor + "20", color: selectedAccount.platformColor }}
                >
                  {selectedAccount.platformName.charAt(0)}
                </div>
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
              <Button 
                variant="secondary" 
                size="sm" 
                icon={<Shield className="h-4 w-4" />}
                onClick={() => handleVerifyAccount(selectedAccount.id)}
              >
                Test Connection
              </Button>
              <Button variant="secondary" size="sm" icon={<RefreshCw className="h-4 w-4" />}>Refresh Token</Button>
              <Button 
                variant="ghost" 
                size="sm" 
                icon={<Pencil className="h-4 w-4" />}
                onClick={() => handleEditClick(selectedAccount)}
              >
                Edit
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Add/Edit Account Modal */}
      <Modal 
        isOpen={showAdd} 
        onClose={() => {
          setShowAdd(false);
          setIsEdit(false);
          setEditId(null);
          setFormPlatformId("");
          setFormAccountName("");
          setFormHandle("");
          setFormProfileUrl("");
          setFormApiKey("");
          setFormApiSecret("");
          setFormAccessToken("");
        }} 
        title={isEdit ? "Edit Social Account" : "Add Social Account"} 
        size="md"
      >
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Platform</label>
            <select 
              value={formPlatformId}
              onChange={(e) => setFormPlatformId(e.target.value)}
              disabled={isEdit}
              className="w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-purple-500/50 disabled:opacity-50"
            >
              <option value="">Select a platform...</option>
              {dbPlatforms
                .filter((p) => (p.slug || "").toLowerCase() !== "tiktok")
                .map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
            </select>
          </div>
          {formPlatformId && (() => {
            const selectedPlat = dbPlatforms.find(p => p.id === formPlatformId);
            const slug = (selectedPlat?.slug || "").toLowerCase();
            if (slug === "facebook") {
              return (
                <div className="rounded-xl bg-blue-500/10 border border-blue-500/20 p-4 text-xs text-blue-300 space-y-3">
                  <div>
                    <p className="font-semibold text-sm text-white mb-1">Easy One-Click Connection (Recommended):</p>
                    <p className="text-gray-300 mb-3">Connect your Facebook Page automatically. No developer access tokens or page IDs needed.</p>
                    <Button 
                      onClick={handleFacebookOAuth} 
                      disabled={isLoading}
                      className="w-full justify-center bg-[#1877F2] hover:bg-[#1877F2]/90 text-white font-semibold gap-2 py-2.5 rounded-xl text-xs flex items-center shadow-lg border-0"
                    >
                      <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                      </svg>
                      {isLoading ? "Redirecting..." : "Connect Facebook Page"}
                    </Button>
                  </div>
                  
                  <div className="border-t border-blue-500/20 pt-2.5">
                    <p className="font-semibold text-white mb-1">Manual Developer Connection:</p>
                    <p>Or configure manually below by pasting your Meta Access Token and typing your account details.</p>
                  </div>
                </div>
              );
            }
            if (slug === "linkedin") {
              return (
                <div className="rounded-xl bg-[#0A66C2]/10 border border-[#0A66C2]/20 p-4 text-xs text-blue-200 space-y-3">
                  <div>
                    <p className="font-semibold text-sm text-white mb-1">Easy One-Click Connection (Recommended):</p>
                    <p className="text-gray-300 mb-3">Sign in with LinkedIn to connect an account. Choose where posts should be published:</p>
                    <div className="grid grid-cols-1 gap-2">
                      <Button
                        onClick={() => handleLinkedinOAuth("personal")}
                        disabled={isLoading}
                        className="w-full justify-center bg-[#0A66C2] hover:bg-[#0A66C2]/90 text-white font-semibold gap-2 py-2.5 rounded-xl text-xs flex items-center shadow-lg border-0"
                      >
                        <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                          <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.225 0z"/>
                        </svg>
                        {isLoading ? "Redirecting..." : "Connect Personal Profile"}
                      </Button>
                      <Button
                        onClick={() => handleLinkedinOAuth("organization")}
                        disabled={isLoading}
                        variant="secondary"
                        className="w-full justify-center gap-2 py-2.5 rounded-xl text-xs flex items-center"
                      >
                        {isLoading ? "Redirecting..." : "Connect Company Page"}
                      </Button>
                    </div>
                  </div>
                  <div className="border-t border-[#0A66C2]/20 pt-2.5 space-y-1">
                    <p className="text-gray-300"><strong className="text-white">Personal Profile</strong> works out of the box. <strong className="text-white">Company Page</strong> requires the "Community Management API" product enabled on your LinkedIn app and admin rights on the page.</p>
                    <p className="text-amber-300/90">Note: LinkedIn Job postings and Ads require a separate LinkedIn partnership approval and aren't available via a standard app yet.</p>
                  </div>
                </div>
              );
            }
            if (slug === "instagram") {
              return (
                <div className="rounded-xl bg-pink-500/10 border border-pink-500/20 p-4 text-xs text-pink-300 space-y-3">
                  <div>
                    <p className="font-semibold text-sm text-white mb-1">Easy One-Click Connection (Recommended):</p>
                    <p className="text-gray-300 mb-3">Connect your Instagram Business or Creator account automatically in one click.</p>
                    <Button 
                      onClick={handleInstagramOAuth} 
                      disabled={isLoading}
                      className="w-full justify-center bg-gradient-to-r from-[#F9CE34] via-[#EE2A7B] to-[#6228D7] hover:opacity-90 text-white font-semibold gap-2 py-2.5 rounded-xl text-xs flex items-center shadow-lg border-0"
                    >
                      <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.051C.014 8.333 0 8.741 0 12s.014 3.667.072 4.947c.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072s3.667-.014 4.947-.072c4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/>
                      </svg>
                      {isLoading ? "Redirecting..." : "Connect Instagram Account"}
                    </Button>
                  </div>
                  
                  <div className="border-t border-pink-500/20 pt-2.5">
                    <p className="font-semibold text-white mb-1">Manual Developer Connection:</p>
                    <p>Or configure manually below by pasting your Meta Access Token and typing your account details.</p>
                  </div>
                </div>
              );
            }
            if (slug === "twitter" || slug === "x") {
              return (
                <div className="rounded-xl bg-black/30 border border-white/20 p-4 text-xs text-gray-200 space-y-3">
                  <div>
                    <p className="font-semibold text-sm text-white mb-1">Easy One-Click Connection (Recommended):</p>
                    <p className="text-gray-300 mb-3">Sign in with X to connect an account and post tweets automatically.</p>
                    <Button
                      onClick={handleTwitterOAuth}
                      disabled={isLoading}
                      className="w-full justify-center bg-black hover:bg-black/80 text-white font-semibold gap-2 py-2.5 rounded-xl text-xs flex items-center shadow-lg border border-white/20"
                    >
                      <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                      {isLoading ? "Redirecting..." : "Connect X (Twitter) Account"}
                    </Button>
                  </div>
                  <div className="border-t border-white/15 pt-2.5">
                    <p className="text-amber-300/90">Note: Text tweets are supported. Image/video upload isn't available yet, and X's free API tier heavily rate-limits posting — a paid X API plan may be required for reliable publishing.</p>
                  </div>
                </div>
              );
            }
            if (slug === "youtube") {
              return (
                <div className="rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 p-4 text-xs text-red-200 space-y-3">
                  <div>
                    <p className="font-semibold text-sm text-white mb-1">Easy One-Click Connection (Recommended):</p>
                    <p className="text-gray-300 mb-3">Sign in with Google to connect your YouTube channel and upload videos.</p>
                    <Button
                      onClick={handleYoutubeOAuth}
                      disabled={isLoading}
                      className="w-full justify-center bg-[#FF0000] hover:bg-[#FF0000]/90 text-white font-semibold gap-2 py-2.5 rounded-xl text-xs flex items-center shadow-lg border-0"
                    >
                      <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                      </svg>
                      {isLoading ? "Redirecting..." : "Connect YouTube Channel"}
                    </Button>
                  </div>
                  <div className="border-t border-[#FF0000]/20 pt-2.5">
                    <p className="text-amber-300/90">Note: "Publishing" to YouTube uploads a <strong className="text-white">video</strong> (attach one to your post). While your Google app is unverified, uploads may be forced to private until you complete Google's verification.</p>
                  </div>
                </div>
              );
            }
            return null;
          })()}
          <Input 
            label="Account Name" 
            placeholder="e.g., My Client's Instagram" 
            value={formAccountName}
            onChange={(e) => setFormAccountName(e.target.value)}
          />
          <Input 
            label="Handle / Username" 
            placeholder="e.g., @mycompany" 
            value={formHandle}
            onChange={(e) => setFormHandle(e.target.value)}
          />
          <Input 
            label="Profile URL" 
            placeholder="https://..." 
            value={formProfileUrl}
            onChange={(e) => setFormProfileUrl(e.target.value)}
          />
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <h4 className="mb-3 text-sm font-medium text-white flex items-center gap-2">
              <Key className="h-4 w-4 text-purple-400" /> API Credentials
            </h4>
            <div className="space-y-3">
              <Input 
                label="API Key" 
                placeholder="Your API key" 
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
              />
              <Input 
                label="API Secret" 
                type="password" 
                placeholder="Your API secret" 
                value={formApiSecret}
                onChange={(e) => setFormApiSecret(e.target.value)}
              />
              <Input 
                label="Access Token" 
                type="password" 
                placeholder={isEdit ? "Paste new Access Token to update" : "OAuth access token"} 
                value={formAccessToken}
                onChange={(e) => setFormAccessToken(e.target.value)}
              />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" onClick={() => {
              setShowAdd(false);
              setIsEdit(false);
              setEditId(null);
            }}>Cancel</Button>
            <Button 
              icon={isEdit ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />} 
              onClick={isEdit ? handleUpdateAccount : handleAddAccount}
              disabled={isLoading || !formPlatformId || !formAccountName}
            >
              {isLoading ? (isEdit ? "Saving..." : "Adding...") : (isEdit ? "Save Changes" : "Add Account")}
            </Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
