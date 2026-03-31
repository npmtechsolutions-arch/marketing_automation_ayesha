import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Pencil,
  Trash2,
  Users,
  Calendar,
  Globe,
  Share2,
  Megaphone,
  X,
  GripVertical,
  Layers,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Toggle } from "@/components/ui/Toggle";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, formatDate, getInitials } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────

interface ApiConfigField {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "number";
  required: boolean;
}

interface SocialPlatform {
  id: string;
  name: string;
  slug: string;
  color: string;
  icon: string;
  description: string;
  baseUrl: string;
  apiConfigTemplate: ApiConfigField[];
  accountsCount: number;
  isActive: boolean;
  createdAt: string;
}

// ── Constants ──────────────────────────────────────────────────────

const PRESET_COLORS = [
  "#1877F2",
  "#E4405F",
  "#0A66C2",
  "#1DA1F2",
  "#FF0000",
  "#00F2EA",
  "#BD081C",
  "#8134AF",
  "#25D366",
  "#FF6900",
  "#6366F1",
  "#EC4899",
];

const ICON_OPTIONS = [
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "twitter", label: "X / Twitter" },
  { value: "youtube", label: "YouTube" },
  { value: "tiktok", label: "TikTok" },
  { value: "pinterest", label: "Pinterest" },
  { value: "globe", label: "Globe" },
  { value: "share2", label: "Share" },
  { value: "megaphone", label: "Megaphone" },
  { value: "layers", label: "Layers" },
];

const FIELD_TYPE_OPTIONS = [
  { value: "text", label: "Text" },
  { value: "password", label: "Password" },
  { value: "url", label: "URL" },
  { value: "number", label: "Number" },
];

// ── Mock Data ──────────────────────────────────────────────────────

const mockPlatforms: SocialPlatform[] = [
  {
    id: "1",
    name: "Facebook",
    slug: "facebook",
    color: "#1877F2",
    icon: "facebook",
    description: "Meta's primary social network for pages, groups, and advertising.",
    baseUrl: "https://graph.facebook.com/v18.0",
    apiConfigTemplate: [
      { key: "app_id", label: "App ID", type: "text", required: true },
      { key: "app_secret", label: "App Secret", type: "password", required: true },
      { key: "access_token", label: "Access Token", type: "password", required: true },
      { key: "page_id", label: "Page ID", type: "text", required: true },
    ],
    accountsCount: 4,
    isActive: true,
    createdAt: "2025-09-15",
  },
  {
    id: "2",
    name: "Instagram",
    slug: "instagram",
    color: "#E4405F",
    icon: "instagram",
    description: "Photo and video sharing platform with Reels and Stories features.",
    baseUrl: "https://graph.instagram.com/v18.0",
    apiConfigTemplate: [
      { key: "access_token", label: "Access Token", type: "password", required: true },
      { key: "business_account_id", label: "Business Account ID", type: "text", required: true },
    ],
    accountsCount: 3,
    isActive: true,
    createdAt: "2025-09-15",
  },
  {
    id: "3",
    name: "LinkedIn",
    slug: "linkedin",
    color: "#0A66C2",
    icon: "linkedin",
    description: "Professional networking platform for B2B marketing and thought leadership.",
    baseUrl: "https://api.linkedin.com/v2",
    apiConfigTemplate: [
      { key: "client_id", label: "Client ID", type: "text", required: true },
      { key: "client_secret", label: "Client Secret", type: "password", required: true },
      { key: "access_token", label: "Access Token", type: "password", required: true },
      { key: "organization_id", label: "Organization ID", type: "text", required: false },
    ],
    accountsCount: 2,
    isActive: true,
    createdAt: "2025-10-01",
  },
  {
    id: "4",
    name: "X / Twitter",
    slug: "twitter",
    color: "#1DA1F2",
    icon: "twitter",
    description: "Real-time microblogging platform for brand engagement and trending topics.",
    baseUrl: "https://api.twitter.com/2",
    apiConfigTemplate: [
      { key: "api_key", label: "API Key", type: "password", required: true },
      { key: "api_secret", label: "API Secret", type: "password", required: true },
      { key: "bearer_token", label: "Bearer Token", type: "password", required: true },
      { key: "access_token", label: "Access Token", type: "password", required: true },
      { key: "access_token_secret", label: "Access Token Secret", type: "password", required: true },
    ],
    accountsCount: 3,
    isActive: true,
    createdAt: "2025-10-01",
  },
  {
    id: "5",
    name: "YouTube",
    slug: "youtube",
    color: "#FF0000",
    icon: "youtube",
    description: "Video hosting platform for long-form content, Shorts, and live streaming.",
    baseUrl: "https://www.googleapis.com/youtube/v3",
    apiConfigTemplate: [
      { key: "api_key", label: "API Key", type: "password", required: true },
      { key: "client_id", label: "OAuth Client ID", type: "text", required: true },
      { key: "client_secret", label: "OAuth Client Secret", type: "password", required: true },
      { key: "channel_id", label: "Channel ID", type: "text", required: true },
    ],
    accountsCount: 1,
    isActive: true,
    createdAt: "2025-11-12",
  },
  {
    id: "6",
    name: "TikTok",
    slug: "tiktok",
    color: "#00F2EA",
    icon: "tiktok",
    description: "Short-form video platform for viral content and younger demographics.",
    baseUrl: "https://open.tiktokapis.com/v2",
    apiConfigTemplate: [
      { key: "client_key", label: "Client Key", type: "text", required: true },
      { key: "client_secret", label: "Client Secret", type: "password", required: true },
      { key: "access_token", label: "Access Token", type: "password", required: true },
    ],
    accountsCount: 2,
    isActive: false,
    createdAt: "2025-12-05",
  },
];

// ── Helpers ────────────────────────────────────────────────────────

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)+/g, "");
}

function getIconComponent(icon: string, size = 18) {
  switch (icon) {
    case "globe":
      return <Globe size={size} />;
    case "share2":
      return <Share2 size={size} />;
    case "megaphone":
      return <Megaphone size={size} />;
    case "layers":
      return <Layers size={size} />;
    default:
      return null;
  }
}

function PlatformIconCircle({ platform }: { platform: SocialPlatform }) {
  const lucideIcon = getIconComponent(platform.icon, 20);
  return (
    <div
      className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
      style={{ backgroundColor: `${platform.color}25`, color: platform.color }}
    >
      {lucideIcon || getInitials(platform.name)}
    </div>
  );
}

// ── Animation Variants ─────────────────────────────────────────────

const stagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

// ── Empty Form State ───────────────────────────────────────────────

const emptyForm: Omit<SocialPlatform, "id" | "accountsCount" | "createdAt"> = {
  name: "",
  slug: "",
  color: PRESET_COLORS[0],
  icon: "globe",
  description: "",
  baseUrl: "",
  apiConfigTemplate: [
    { key: "", label: "", type: "text", required: true },
  ],
  isActive: true,
};

// ── Platform Card ──────────────────────────────────────────────────

function PlatformCard({
  platform,
  onEdit,
  onDelete,
  onManageAccounts,
}: {
  platform: SocialPlatform;
  onEdit: () => void;
  onDelete: () => void;
  onManageAccounts: () => void;
}) {
  return (
    <GlassCard hover className="relative overflow-hidden group">
      {/* Color accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
        style={{ backgroundColor: platform.color }}
      />

      <div className="pt-2">
        {/* Header row */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <PlatformIconCircle platform={platform} />
            <div>
              <h3 className="text-white font-semibold text-base">{platform.name}</h3>
              <Badge
                variant={platform.isActive ? "success" : "default"}
                dot
                size="sm"
              >
                {platform.isActive ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-gray-400 line-clamp-2 mb-4 min-h-[2.5rem]">
          {platform.description}
        </p>

        {/* Stats row */}
        <div className="flex items-center justify-between text-xs text-gray-500 mb-4 pb-4 border-b border-white/5">
          <span className="flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" />
            {platform.accountsCount} account{platform.accountsCount !== 1 ? "s" : ""} connected
          </span>
          <span className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" />
            {formatDate(platform.createdAt)}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            className="flex-1"
            onClick={onManageAccounts}
          >
            Manage Accounts
          </Button>
          <button
            onClick={onEdit}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </GlassCard>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<SocialPlatform[]>(mockPlatforms);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingPlatform, setEditingPlatform] = useState<SocialPlatform | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingPlatform, setDeletingPlatform] = useState<SocialPlatform | null>(null);

  // Form state
  const [form, setForm] = useState(emptyForm);
  const [customColor, setCustomColor] = useState("");

  const totalAccounts = useMemo(
    () => platforms.reduce((sum, p) => sum + p.accountsCount, 0),
    [platforms]
  );
  // Use in subtitle
  void totalAccounts;

  // ── Handlers ─────────────────────────────────────────────────────

  function openCreateModal() {
    setEditingPlatform(null);
    setForm({ ...emptyForm, apiConfigTemplate: [{ key: "", label: "", type: "text", required: true }] });
    setCustomColor("");
    setShowModal(true);
  }

  function openEditModal(platform: SocialPlatform) {
    setEditingPlatform(platform);
    setForm({
      name: platform.name,
      slug: platform.slug,
      color: platform.color,
      icon: platform.icon,
      description: platform.description,
      baseUrl: platform.baseUrl,
      apiConfigTemplate: [...platform.apiConfigTemplate],
      isActive: platform.isActive,
    });
    setCustomColor(
      PRESET_COLORS.includes(platform.color) ? "" : platform.color
    );
    setShowModal(true);
  }

  function handleSave() {
    if (editingPlatform) {
      setPlatforms((prev) =>
        prev.map((p) =>
          p.id === editingPlatform.id
            ? { ...p, ...form, apiConfigTemplate: form.apiConfigTemplate.filter((f) => f.key && f.label) }
            : p
        )
      );
    } else {
      const newPlatform: SocialPlatform = {
        ...form,
        id: Date.now().toString(),
        accountsCount: 0,
        createdAt: new Date().toISOString(),
        apiConfigTemplate: form.apiConfigTemplate.filter((f) => f.key && f.label),
      };
      setPlatforms((prev) => [...prev, newPlatform]);
    }
    setShowModal(false);
  }

  function confirmDelete() {
    if (deletingPlatform) {
      setPlatforms((prev) => prev.filter((p) => p.id !== deletingPlatform.id));
    }
    setShowDeleteModal(false);
    setDeletingPlatform(null);
  }

  function handleNameChange(name: string) {
    setForm((prev) => ({
      ...prev,
      name,
      slug: editingPlatform ? prev.slug : slugify(name),
    }));
  }

  function addTemplateField() {
    setForm((prev) => ({
      ...prev,
      apiConfigTemplate: [
        ...prev.apiConfigTemplate,
        { key: "", label: "", type: "text", required: false },
      ],
    }));
  }

  function removeTemplateField(index: number) {
    setForm((prev) => ({
      ...prev,
      apiConfigTemplate: prev.apiConfigTemplate.filter((_, i) => i !== index),
    }));
  }

  function updateTemplateField(index: number, updates: Partial<ApiConfigField>) {
    setForm((prev) => ({
      ...prev,
      apiConfigTemplate: prev.apiConfigTemplate.map((f, i) =>
        i === index ? { ...f, ...updates } : f
      ),
    }));
  }

  // ── Render ───────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8"
      >
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold text-white">Social Platforms</h1>
            <Badge variant="info">
              {platforms.length} platform{platforms.length !== 1 ? "s" : ""} configured
            </Badge>
          </div>
          <p className="text-gray-400 mt-1">
            Define and manage the social media platforms your agency works with
          </p>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={openCreateModal}
        >
          Add Platform
        </Button>
      </motion.div>

      {/* Content */}
      {platforms.length === 0 ? (
        <GlassCard>
          <EmptyState
            icon={<Layers className="w-7 h-7" />}
            title="No platforms yet"
            description="Create your first social media platform to start connecting accounts and scheduling posts."
            actionLabel="Create Your First Platform"
            onAction={openCreateModal}
          />
        </GlassCard>
      ) : (
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
        >
          {platforms.map((platform) => (
            <motion.div key={platform.id} variants={fadeUp}>
              <PlatformCard
                platform={platform}
                onEdit={() => openEditModal(platform)}
                onDelete={() => {
                  setDeletingPlatform(platform);
                  setShowDeleteModal(true);
                }}
                onManageAccounts={() => {
                  /* navigate to accounts filtered by platform */
                }}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* ── Add/Edit Platform Modal ──────────────────────────────── */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingPlatform ? "Edit Platform" : "Create Platform"}
        size="xl"
      >
        <div className="space-y-6">
          {/* Name + Slug row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Platform Name"
              placeholder="e.g. Facebook, Custom Platform"
              value={form.name}
              onChange={(e) => handleNameChange(e.target.value)}
            />
            <Input
              label="Slug"
              placeholder="platform-slug"
              value={form.slug}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, slug: slugify(e.target.value) }))
              }
            />
          </div>

          {/* Color Picker */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-2 pl-1">
              Platform Color
            </label>
            <div className="flex flex-wrap items-center gap-2">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => {
                    setForm((prev) => ({ ...prev, color }));
                    setCustomColor("");
                  }}
                  className={cn(
                    "w-8 h-8 rounded-full border-2 transition-all duration-200 hover:scale-110",
                    form.color === color && !customColor
                      ? "border-white scale-110 ring-2 ring-white/20"
                      : "border-transparent"
                  )}
                  style={{ backgroundColor: color }}
                />
              ))}
              {/* Custom hex */}
              <div className="flex items-center gap-2 ml-2">
                <div
                  className={cn(
                    "w-8 h-8 rounded-full border-2 transition-all",
                    customColor
                      ? "border-white ring-2 ring-white/20"
                      : "border-white/20"
                  )}
                  style={{
                    backgroundColor: customColor || "#333",
                  }}
                />
                <input
                  type="text"
                  placeholder="#HEX"
                  value={customColor}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCustomColor(val);
                    if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                      setForm((prev) => ({ ...prev, color: val }));
                    }
                  }}
                  className="w-24 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 outline-none focus:border-purple-500/50"
                />
              </div>
            </div>
          </div>

          {/* Icon + Active Toggle row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
            <Select
              label="Icon"
              options={ICON_OPTIONS}
              value={form.icon}
              onChange={(val) => setForm((prev) => ({ ...prev, icon: val }))}
            />
            <div className="pb-1">
              <Toggle
                label="Active"
                description="Enable posting to this platform"
                checked={form.isActive}
                onCheckedChange={(val) =>
                  setForm((prev) => ({ ...prev, isActive: val }))
                }
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, description: e.target.value }))
              }
              placeholder="Brief description of this platform..."
              rows={3}
              className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all duration-200 resize-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 placeholder-gray-500"
            />
          </div>

          {/* Base URL */}
          <Input
            label="API Base URL"
            placeholder="https://api.platform.com/v1"
            value={form.baseUrl}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, baseUrl: e.target.value }))
            }
          />

          {/* API Config Template Fields */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <label className="block text-xs font-medium text-gray-400 pl-1">
                  API Configuration Template
                </label>
                <p className="text-[11px] text-gray-500 mt-0.5 pl-1">
                  Define the fields accounts will need to fill in
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={<Plus className="w-3.5 h-3.5" />}
                onClick={addTemplateField}
              >
                Add Field
              </Button>
            </div>

            <div className="space-y-3">
              <AnimatePresence>
                {form.apiConfigTemplate.map((field, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="flex items-start gap-2 p-3 rounded-xl bg-white/[0.03] border border-white/5">
                      <div className="pt-2.5 text-gray-600">
                        <GripVertical className="w-4 h-4" />
                      </div>
                      <div className="flex-1 grid grid-cols-1 sm:grid-cols-4 gap-2">
                        <Input
                          placeholder="Field key"
                          value={field.key}
                          onChange={(e) =>
                            updateTemplateField(idx, { key: e.target.value })
                          }
                        />
                        <Input
                          placeholder="Display label"
                          value={field.label}
                          onChange={(e) =>
                            updateTemplateField(idx, { label: e.target.value })
                          }
                        />
                        <Select
                          options={FIELD_TYPE_OPTIONS}
                          value={field.type}
                          onChange={(val) =>
                            updateTemplateField(idx, {
                              type: val as ApiConfigField["type"],
                            })
                          }
                          placeholder="Type"
                        />
                        <div className="flex items-center gap-2">
                          <Toggle
                            label="Required"
                            checked={field.required}
                            onCheckedChange={(val) =>
                              updateTemplateField(idx, { required: val })
                            }
                          />
                        </div>
                      </div>
                      <button
                        onClick={() => removeTemplateField(idx)}
                        className="pt-2.5 text-gray-500 hover:text-red-400 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="ghost"
              onClick={() => setShowModal(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={!form.name.trim() || !form.slug.trim()}
            >
              {editingPlatform ? "Save Changes" : "Create Platform"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Delete Confirmation Modal ────────────────────────────── */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setDeletingPlatform(null);
        }}
        title="Delete Platform"
        size="sm"
      >
        <div className="space-y-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center shrink-0">
              <Trash2 className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-sm text-gray-300">
                Are you sure you want to delete{" "}
                <span className="font-semibold text-white">
                  {deletingPlatform?.name}
                </span>
                ? This will remove all associated accounts and cannot be undone.
              </p>
              {deletingPlatform && deletingPlatform.accountsCount > 0 && (
                <p className="text-xs text-amber-400 mt-2">
                  Warning: {deletingPlatform.accountsCount} account
                  {deletingPlatform.accountsCount !== 1 ? "s" : ""} will be
                  disconnected.
                </p>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button
              variant="ghost"
              onClick={() => {
                setShowDeleteModal(false);
                setDeletingPlatform(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete}>
              Delete Platform
            </Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
