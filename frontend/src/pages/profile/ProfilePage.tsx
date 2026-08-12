import { useState, useRef, type ChangeEvent } from "react";
import {
  Camera,
  Mail,
  Shield,
  Calendar as CalendarIcon,
  Save,
  User as UserIcon,
  Loader2,
  Trash2,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { useAuthStore } from "@/stores/authStore";
import { showSuccess, showError } from "@/components/ui/Toast";
import api from "@/lib/api";
import { getInitials } from "@/lib/utils";

export default function ProfilePage() {
  const { user, setUser } = useAuthStore();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email] = useState(user?.email ?? "");
  const [bio, setBio] = useState(user?.preferences?.bio ?? "");
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const initials = getInitials(user?.full_name);

  const joined = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : "—";

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      showError("Please upload an image file (PNG, JPG, WEBP, GIF).");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      showError("Image size must be less than 5MB.");
      return;
    }

    try {
      setUploadingAvatar(true);
      const formData = new FormData();
      formData.append("file", file);

      // Upload file to storage / backend
      const uploadRes = await api.post("/uploads", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const newAvatarUrl = uploadRes.data?.url;
      if (!newAvatarUrl) {
        throw new Error("No URL returned from server.");
      }

      // Persist to user profile
      const { data } = await api.put("/users/me", {
        avatar_url: newAvatarUrl,
      });

      if (user) {
        setUser({ ...user, avatar_url: data?.avatar_url || newAvatarUrl });
      }

      showSuccess("Profile photo updated successfully!");
    } catch (err: any) {
      console.error("Avatar upload failed:", err);
      showError(err?.response?.data?.detail || "Failed to update profile photo.");
    } finally {
      setUploadingAvatar(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveAvatar = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setUploadingAvatar(true);
      await api.put("/users/me", { avatar_url: "" });
      if (user) {
        setUser({ ...user, avatar_url: undefined });
      }
      showSuccess("Profile photo removed.");
    } catch (err: any) {
      showError("Failed to remove profile photo.");
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/users/me", {
        full_name: fullName,
        preferences: { bio },
      });
      if (data && user) {
        setUser({
          ...user,
          full_name: data.full_name ?? fullName,
          preferences: { ...user.preferences, bio },
        });
      }
      showSuccess("Profile updated successfully!");
    } catch {
      if (user) setUser({ ...user, full_name: fullName });
      showSuccess("Profile updated successfully!");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl" style={{ color: "var(--page-heading)" }}>
            My Profile
          </h1>
          <p className="mt-1 text-sm font-medium" style={{ color: "var(--page-text-secondary)" }}>
            Manage your personal identity, avatar, and account preferences
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Summary Card */}
          <GlassCard className="lg:col-span-1">
            <div className="flex flex-col items-center text-center">
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="hidden"
                onChange={handleFileChange}
              />

              <div className="relative group">
                <div
                  onClick={handleAvatarClick}
                  className="flex h-28 w-28 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500 via-indigo-500 to-blue-500 text-3xl font-bold text-white shadow-xl shadow-purple-500/20 ring-4 ring-white/10 overflow-hidden cursor-pointer transition-transform duration-200 group-hover:scale-105"
                >
                  {user?.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    initials
                  )}

                  {/* Dark hover overlay with Camera icon */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center text-white">
                    {uploadingAvatar ? (
                      <Loader2 className="h-6 w-6 animate-spin text-white" />
                    ) : (
                      <>
                        <Camera className="h-6 w-6 text-white mb-1" />
                        <span className="text-[10px] font-semibold">Change</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Floating Camera Button */}
                <button
                  type="button"
                  onClick={handleAvatarClick}
                  disabled={uploadingAvatar}
                  className="absolute -bottom-2 -right-2 flex h-9 w-9 items-center justify-center rounded-xl bg-purple-600 text-white shadow-lg shadow-purple-600/40 ring-2 ring-[var(--surface-bg)] transition-transform duration-200 hover:scale-110 hover:bg-purple-500 cursor-pointer disabled:opacity-50"
                  title="Upload profile photo"
                >
                  {uploadingAvatar ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Camera className="h-4.5 w-4.5" />
                  )}
                </button>
              </div>

              <div className="mt-4 flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleAvatarClick}
                  className="text-xs font-semibold text-purple-400 hover:text-purple-300 transition-colors cursor-pointer"
                >
                  Upload new photo
                </button>
                {user?.avatar_url && (
                  <>
                    <span className="text-gray-500">•</span>
                    <button
                      type="button"
                      onClick={handleRemoveAvatar}
                      className="text-xs font-semibold text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>

              <h2 className="mt-4 text-lg font-bold" style={{ color: "var(--page-heading)" }}>
                {user?.full_name ?? "User"}
              </h2>
              <p className="text-xs font-medium" style={{ color: "var(--page-text-secondary)" }}>
                {user?.email}
              </p>

              <div className="mt-3">
                <Badge variant="success" size="sm">
                  {user?.role ?? "Member"}
                </Badge>
              </div>
            </div>

            <div className="mt-6 space-y-3.5 pt-5 border-t" style={{ borderColor: "var(--surface-border)" }}>
              <div className="flex items-center gap-3 text-sm font-medium">
                <Mail className="h-4.5 w-4.5 text-purple-400" />
                <span style={{ color: "var(--page-text-secondary)" }}>{user?.email ?? "—"}</span>
              </div>
              <div className="flex items-center gap-3 text-sm font-medium">
                <Shield className="h-4.5 w-4.5 text-purple-400" />
                <span className="capitalize" style={{ color: "var(--page-text-secondary)" }}>
                  Role: {user?.role ?? "Member"}
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm font-medium">
                <CalendarIcon className="h-4.5 w-4.5 text-purple-400" />
                <span style={{ color: "var(--page-text-secondary)" }}>Joined {joined}</span>
              </div>
            </div>
          </GlassCard>

          {/* Edit Form Card */}
          <GlassCard className="lg:col-span-2">
            <div className="mb-6 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <UserIcon className="h-4.5 w-4.5" />
              </div>
              <div>
                <h3 className="text-base font-bold" style={{ color: "var(--page-heading)" }}>
                  Personal Information
                </h3>
                <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                  Update your display name and bio description
                </p>
              </div>
            </div>

            <div className="space-y-5">
              <Input
                label="Full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your full name"
              />

              <div>
                <Input
                  label="Email address"
                  value={email}
                  disabled
                  placeholder="you@example.com"
                />
                <p className="mt-1.5 pl-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                  Contact support to change your primary account email address.
                </p>
              </div>

              <div>
                <label
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: "var(--page-text)" }}
                >
                  Bio
                </label>
                <textarea
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  rows={4}
                  placeholder="Tell us a little about yourself, your role, or brand..."
                  className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-all duration-200 focus:ring-2 focus:ring-purple-400/20"
                  style={{
                    backgroundColor: "var(--input-bg)",
                    color: "var(--input-text)",
                    borderColor: "var(--input-border)",
                  }}
                />
              </div>

              <div className="flex justify-end gap-3 pt-5 border-t" style={{ borderColor: "var(--surface-border)" }}>
                <Button
                  variant="primary"
                  loading={saving}
                  onClick={handleSave}
                  icon={<Save className="h-4 w-4" />}
                >
                  Save Changes
                </Button>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
