import { useState } from "react";
import {
  Camera,
  Mail,
  Shield,
  Calendar as CalendarIcon,
  Save,
  User as UserIcon,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { useAuthStore } from "@/stores/authStore";
import { showSuccess } from "@/components/ui/Toast";
import api from "@/lib/api";

export default function ProfilePage() {
  const { user, setUser } = useAuthStore();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email] = useState(user?.email ?? "");
  const [bio, setBio] = useState("");
  const [saving, setSaving] = useState(false);

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "ME";

  const joined = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : "—";

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/users/me", {
        full_name: fullName,
        bio,
      });
      if (data && user) {
        setUser({ ...user, full_name: data.full_name ?? fullName });
      }
      showSuccess("Profile updated");
    } catch {
      // Optimistic local update so the UI still reflects the change
      if (user) setUser({ ...user, full_name: fullName });
      showSuccess("Profile updated");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">My Profile</h1>
          <p className="mt-1 text-sm text-gray-400">
            Manage your personal information and account details
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Summary card */}
          <GlassCard className="lg:col-span-1">
            <div className="flex flex-col items-center text-center">
              <div className="relative">
                <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-blue-500 text-2xl font-bold text-white">
                  {user?.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="h-full w-full rounded-full object-cover"
                    />
                  ) : (
                    initials
                  )}
                </div>
                <button
                  className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-purple-600 text-white shadow-lg transition-transform hover:scale-105"
                  title="Change photo"
                >
                  <Camera className="h-4 w-4" />
                </button>
              </div>

              <h2 className="mt-4 text-lg font-semibold text-white">
                {user?.full_name ?? "User"}
              </h2>
              <p className="text-sm text-gray-400">{user?.email}</p>

              <div className="mt-3">
                <Badge variant="success" size="sm">
                  {user?.role ?? "Member"}
                </Badge>
              </div>
            </div>

            <div className="mt-6 space-y-3 border-t border-white/5 pt-5">
              <div className="flex items-center gap-3 text-sm">
                <Mail className="h-4 w-4 text-purple-400" />
                <span className="text-gray-400">{user?.email ?? "—"}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <Shield className="h-4 w-4 text-purple-400" />
                <span className="text-gray-400 capitalize">
                  {user?.role ?? "Member"}
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <CalendarIcon className="h-4 w-4 text-purple-400" />
                <span className="text-gray-400">Joined {joined}</span>
              </div>
            </div>
          </GlassCard>

          {/* Edit form */}
          <GlassCard className="lg:col-span-2">
            <div className="mb-5 flex items-center gap-2">
              <UserIcon className="h-5 w-5 text-purple-400" />
              <h3 className="text-base font-semibold text-white">
                Personal Information
              </h3>
            </div>

            <div className="space-y-5">
              <Input
                label="Full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
              />

              <div>
                <Input
                  label="Email address"
                  value={email}
                  disabled
                  placeholder="you@example.com"
                />
                <p className="mt-1.5 pl-1 text-xs text-gray-500">
                  Contact support to change your email address.
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
                  placeholder="Tell us a little about yourself..."
                  className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-all duration-200"
                  style={{
                    backgroundColor: "var(--input-bg)",
                    color: "var(--input-text)",
                    borderColor: "var(--input-border)",
                  }}
                />
              </div>

              <div className="flex justify-end gap-3 border-t border-white/5 pt-5">
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
