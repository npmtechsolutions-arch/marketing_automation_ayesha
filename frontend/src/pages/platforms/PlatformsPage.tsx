import { useState, useEffect, useMemo } from "react";
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
import api, { getAccountId } from "@/lib/api";

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

const emptyForm = {
  name: "",
  slug: "",
  color: PRESET_COLORS[0],
  icon: "globe",
  description: "",
  baseUrl: "",
  apiConfigTemplate: [
    { key: "", label: "", type: "text" as const, required: true },
  ],
  isActive: true,
};

// ── Platform Card ──────────────────────────────────────────────────

function PlatformCard({
  platform,
  onEdit,
  onDelete,
}: {
  platform: SocialPlatform;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <GlassCard padding="md" hover>
      <div className="flex items-start justify-between gap-4">
        <div className="flex gap-4">
          <PlatformIconCircle platform={platform} />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-white text-lg">
                {platform.name}
              </h3>
              <Badge variant={platform.isActive ? "success" : "default"}>
                {platform.isActive ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-gray-400 text-sm mt-1 line-clamp-2">
              {platform.description || "No description provided."}
            </p>
            <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5" />
                {platform.accountsCount} Account{platform.accountsCount !== 1 ? "s" : ""}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                Configured {formatDate(platform.createdAt)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="xs"
            onClick={onEdit}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Pencil className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={onDelete}
            className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </GlassCard>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingPlatform, setEditingPlatform] = useState<SocialPlatform | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingPlatform, setDeletingPlatform] = useState<SocialPlatform | null>(null);

  // Form state
  const [form, setForm] = useState(emptyForm);
  const [customColor, setCustomColor] = useState("");

  const fetchPlatforms = async () => {
    const activeAccountId = await getAccountId();
    if (!activeAccountId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res: any = await api.get(`/accounts/${activeAccountId}/social-platforms/`);
      const fetched = res.items || res.data?.items || [];
      const mapped = fetched.map((item: any) => ({
        id: item.id,
        name: item.name,
        slug: item.slug,
        color: item.color || "#6366F1",
        icon: item.icon || "globe",
        description: item.description || "",
        baseUrl: item.base_url || "",
        apiConfigTemplate: item.api_config_template?.fields || [],
        accountsCount: item.social_accounts_count || 0,
        isActive: item.is_active,
        createdAt: item.created_at,
      }));
      setPlatforms(mapped);
    } catch (error) {
      console.error("Error fetching platforms:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatforms();
  }, []);

  const totalAccounts = useMemo(
    () => platforms.reduce((sum, p) => sum + p.accountsCount, 0),
    [platforms]
  );
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

  async function handleSave() {
    if (!accountId) return;
    try {
      const templateFields = form.apiConfigTemplate.filter((f) => f.key && f.label);
      const payload = {
        name: form.name,
        slug: form.slug,
        color: form.color,
        icon: form.icon,
        description: form.description,
        base_url: form.baseUrl,
        api_config_template: { fields: templateFields },
        is_active: form.isActive,
      };

      if (editingPlatform) {
        await api.put(`/accounts/${accountId}/social-platforms/${editingPlatform.id}`, payload);
      } else {
        await api.post(`/accounts/${accountId}/social-platforms/`, payload);
      }
      setShowModal(false);
      await fetchPlatforms();
    } catch (error) {
      console.error("Error saving platform:", error);
    }
  }

  async function confirmDelete() {
    if (!accountId || !deletingPlatform) return;
    try {
      await api.delete(`/accounts/${accountId}/social-platforms/${deletingPlatform.id}`);
      setShowDeleteModal(false);
      setDeletingPlatform(null);
      await fetchPlatforms();
    } catch (error) {
      console.error("Error deleting platform:", error);
    }
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

      {/* Main Grid */}
      {isLoading && platforms.length === 0 ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          Loading platforms...
        </div>
      ) : platforms.length === 0 ? (
        <EmptyState
          icon={<Globe className="w-10 h-10 text-gray-400" />}
          title="No Platforms Configured"
          description="Create your first social media platform configuration to connect accounts."
          action={
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={openCreateModal}
            >
              Configure Platform
            </Button>
          }
        />
      ) : (
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 gap-6"
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
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* ── Add/Edit Platform Modal ────────────────────────────────── */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingPlatform ? "Edit Platform" : "Add Platform"}
        size="lg"
      >
        <div className="space-y-6 max-h-[80vh] overflow-y-auto pr-1">
          {/* General Config */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-purple-400">
              General Info
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Platform Name"
                placeholder="e.g. Meta Ads, Pinterest"
                value={form.name}
                onChange={(e) => handleNameChange(e.target.value)}
              />
              <Input
                label="API Slug"
                placeholder="e.g. meta-ads"
                value={form.slug}
                disabled={!!editingPlatform}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, slug: slugify(e.target.value) }))
                }
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="API Base URL (Optional)"
                placeholder="https://api.platform.com/v1"
                value={form.baseUrl}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, baseUrl: e.target.value }))
                }
              />
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Default Icon
                </label>
                <Select
                  value={form.icon}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, icon: e.target.value }))
                  }
                  options={ICON_OPTIONS}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Platform Color
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {PRESET_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => {
                        setForm((prev) => ({ ...prev, color: c }));
                        setCustomColor("");
                      }}
                      className={cn(
                        "w-6 h-6 rounded-full border transition-all scale-100",
                        form.color === c
                          ? "border-white scale-110 shadow-lg"
                          : "border-transparent hover:scale-105"
                      )}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
                <Input
                  placeholder="Or enter custom Hex color (#FF00FF)"
                  value={customColor}
                  onChange={(e) => {
                    setCustomColor(e.target.value);
                    if (e.target.value.match(/^#[0-9A-Fa-f]{6}$/)) {
                      setForm((prev) => ({ ...prev, color: e.target.value }));
                    }
                  }}
                />
              </div>
              <div className="flex flex-col justify-end">
                <Toggle
                  label="Is Platform Active"
                  checked={form.isActive}
                  onChange={(checked) =>
                    setForm((prev) => ({ ...prev, isActive: checked }))
                  }
                />
              </div>
            </div>
            <Input
              label="Description"
              placeholder="Brief description of what this platform is used for..."
              value={form.description}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, description: e.target.value }))
              }
            />
          </div>

          <hr className="border-white/5" />

          {/* Config Template Fields */}
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-purple-400">
                  API Account Config Template
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Define the fields required when a user adds their account details
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={addTemplateField}
                icon={<Plus className="w-3.5 h-3.5" />}
              >
                Add Field
              </Button>
            </div>

            <div className="space-y-3">
              <AnimatePresence>
                {form.apiConfigTemplate.map((field, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className="flex gap-3 items-end bg-white/5 p-3 rounded-xl border border-white/5"
                  >
                    <div className="w-6 shrink-0 flex items-center justify-center cursor-grab text-gray-500 pb-2.5">
                      <GripVertical className="w-4 h-4" />
                    </div>
                    <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <Input
                        label="Field Key (Internal)"
                        placeholder="app_id"
                        value={field.key}
                        onChange={(e) =>
                          updateTemplateField(i, { key: slugify(e.target.value) })
                        }
                      />
                      <Input
                        label="Field Label"
                        placeholder="App ID"
                        value={field.label}
                        onChange={(e) =>
                          updateTemplateField(i, { label: e.target.value })
                        }
                      />
                      <div>
                        <label className="block text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">
                          Type
                        </label>
                        <Select
                          value={field.type}
                          onChange={(e: any) =>
                            updateTemplateField(i, { type: e.target.value })
                          }
                          options={FIELD_TYPE_OPTIONS}
                        />
                      </div>
                      <div className="flex items-center justify-center pb-2.5">
                        <Toggle
                          label="Required"
                          checked={field.required}
                          onChange={(checked) =>
                            updateTemplateField(i, { required: checked })
                          }
                        />
                      </div>
                    </div>
                    <div className="shrink-0 pb-1.5">
                      <button
                        onClick={() => removeTemplateField(i)}
                        disabled={form.apiConfigTemplate.length === 1}
                        className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                      >
                        <Trash2 className="w-4 h-4" />
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
