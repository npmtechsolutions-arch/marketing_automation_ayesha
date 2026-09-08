import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  ChevronRight,
  Film,
  FolderPlus,
  Folder as FolderIcon,
  Image as ImageIcon,
  Loader2,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { showError, showSuccess } from "@/components/ui/Toast";
import {
  createFolder,
  deleteFolder,
  deleteMedia,
  errorDetail,
  formatBytes,
  listFolders,
  listMedia,
  moveMedia,
  updateMedia,
  uploadFile,
  type MediaFolder,
  type MediaItem,
} from "@/lib/media";
import { cn } from "@/lib/utils";

type Upload = { id: string; name: string; percent: number; error?: string };

export default function MediaLibraryPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [folders, setFolders] = useState<MediaFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [storage, setStorage] = useState({ used: 0, limit: null as number | null });

  const [folderId, setFolderId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("all");
  const [sort, setSort] = useState<"date" | "name" | "size">("date");

  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState<MediaItem | null>(null);
  const dragDepth = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [media, tree] = await Promise.all([
        listMedia({ search, kind, folder_id: folderId, sort, order: sort === "name" ? "asc" : "desc" }),
        listFolders(),
      ]);
      setItems(media.items);
      setFolders(tree);
      setStorage({ used: media.storage_used_bytes, limit: media.storage_limit_bytes });
    } catch (err: any) {
      showError(errorDetail(err, "Could not load the media library."));
    }
    setLoading(false);
  }, [search, kind, folderId, sort]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  // --- uploading ----------------------------------------------------------

  const startUploads = async (files: File[]) => {
    for (const file of files) {
      const id = `${file.name}-${Date.now()}-${Math.random()}`;
      setUploads((current) => [...current, { id, name: file.name, percent: 0 }]);
      try {
        await uploadFile(file, {
          folderId,
          onProgress: (percent) =>
            setUploads((current) =>
              current.map((u) => (u.id === id ? { ...u, percent } : u))
            ),
        });
        setUploads((current) => current.filter((u) => u.id !== id));
      } catch (err: any) {
        // Kept in the list rather than toasted away: with several files in
        // flight, a toast cannot say which one failed.
        const message = errorDetail(err, "Upload failed.");
        setUploads((current) =>
          current.map((u) => (u.id === id ? { ...u, error: message } : u))
        );
      }
    }
    await load();
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    startUploads(Array.from(event.dataTransfer.files));
  };

  // --- folders ------------------------------------------------------------

  const addFolder = async () => {
    const name = window.prompt("Folder name");
    if (!name?.trim()) return;
    try {
      await createFolder(name.trim(), folderId);
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not create the folder."));
    }
  };

  const removeFolder = async (folder: MediaFolder) => {
    if (
      !window.confirm(
        `Delete "${folder.name}"? Its ${folder.media_count} file(s) move to the library root.`
      )
    )
      return;
    try {
      await deleteFolder(folder.id);
      if (folderId === folder.id) setFolderId(null);
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not delete the folder."));
    }
  };

  const remove = async (item: MediaItem) => {
    const warning = item.used_in_posts
      ? `"${item.filename}" is used by ${item.used_in_posts} post(s). It will be removed from the library but kept so those posts still work. Continue?`
      : `Delete "${item.filename}"?`;
    if (!window.confirm(warning)) return;
    try {
      showSuccess(await deleteMedia(item.id));
      await load();
    } catch (err: any) {
      showError(errorDetail(err, "Could not delete that file."));
    }
  };

  const rootFolders = folders.filter((f) => !f.parent_id);
  const childrenOf = (id: string) => folders.filter((f) => f.parent_id === id);
  const percentUsed =
    storage.limit && storage.limit > 0
      ? Math.min(100, (storage.used / storage.limit) * 100)
      : 0;

  const renderFolder = (folder: MediaFolder, depth = 0) => (
    <div key={folder.id}>
      <div
        className={cn(
          "group flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer text-sm",
          folderId === folder.id && "bg-purple-500/10"
        )}
        style={{ paddingLeft: `${8 + depth * 14}px`, color: "var(--page-text)" }}
        onClick={() => setFolderId(folder.id)}
      >
        <FolderIcon className="w-4 h-4 shrink-0 text-purple-400" />
        <span className="truncate flex-1">{folder.name}</span>
        <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>
          {folder.media_count}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            removeFolder(folder);
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Trash2 className="w-3 h-3 text-red-400" />
        </button>
      </div>
      {childrenOf(folder.id).map((child) => renderFolder(child, depth + 1))}
    </div>
  );

  return (
    <DashboardLayout>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-6"
        onDragEnter={(e) => {
          e.preventDefault();
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragLeave={() => {
          // Counted rather than toggled: dragging over a child element fires
          // leave on the parent, which would flicker the overlay off.
          dragDepth.current -= 1;
          if (dragDepth.current <= 0) setDragging(false);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Media library
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--page-text-secondary)" }}>
              {formatBytes(storage.used)}
              {storage.limit ? ` of ${formatBytes(storage.limit)} used` : " used"}
            </p>
            {storage.limit ? (
              <div
                className="h-1.5 w-56 rounded-full mt-2 overflow-hidden"
                style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
              >
                <div
                  className={cn(
                    "h-full rounded-full",
                    percentUsed > 90
                      ? "bg-red-500"
                      : percentUsed > 75
                        ? "bg-amber-500"
                        : "bg-gradient-to-r from-purple-500 to-blue-500"
                  )}
                  style={{ width: `${percentUsed}%` }}
                />
              </div>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" icon={<FolderPlus className="w-4 h-4" />} onClick={addFolder}>
              New folder
            </Button>
            <label>
              <input
                type="file"
                multiple
                accept="image/*,video/*"
                className="hidden"
                onChange={(e) => startUploads(Array.from(e.target.files ?? []))}
              />
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium cursor-pointer bg-gradient-to-r from-purple-500 to-blue-500 text-white">
                <Upload className="w-4 h-4" />
                Upload
              </span>
            </label>
          </div>
        </div>

        {uploads.length > 0 && (
          <GlassCard className="p-4 space-y-2">
            {uploads.map((upload) => (
              <div key={upload.id} className="text-xs">
                <div className="flex justify-between mb-1">
                  <span className="truncate" style={{ color: "var(--page-text)" }}>
                    {upload.name}
                  </span>
                  <span style={{ color: upload.error ? undefined : "var(--page-text-muted)" }}
                        className={upload.error ? "text-red-400" : undefined}>
                    {upload.error ?? `${upload.percent}%`}
                  </span>
                </div>
                {!upload.error && (
                  <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--sidebar-hover-bg)" }}>
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all"
                      style={{ width: `${upload.percent}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </GlassCard>
        )}

        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <GlassCard className="p-3 h-fit">
            <div
              className={cn(
                "flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer text-sm",
                folderId === null && "bg-purple-500/10"
              )}
              style={{ color: "var(--page-text)" }}
              onClick={() => setFolderId(null)}
            >
              <ChevronRight className="w-4 h-4 text-purple-400" />
              <span className="flex-1">All files</span>
            </div>
            {rootFolders.map((folder) => renderFolder(folder))}
          </GlassCard>

          <div className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <div className="flex-1 min-w-[200px]">
                <Input
                  placeholder="Search by filename or tag…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  icon={<Search className="w-4 h-4" />}
                />
              </div>
              {(
                [
                  ["all", "All"],
                  ["image", "Images"],
                  ["video", "Video"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setKind(value)}
                  className={cn(
                    "px-3 py-2 rounded-xl text-sm",
                    kind === value && "bg-purple-500/15 text-purple-300"
                  )}
                  style={kind === value ? undefined : { color: "var(--page-text-secondary)" }}
                >
                  {label}
                </button>
              ))}
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as typeof sort)}
                className="px-3 py-2 rounded-xl text-sm"
                style={{
                  backgroundColor: "var(--input-bg)",
                  color: "var(--page-text)",
                  border: "1px solid var(--surface-border)",
                }}
              >
                <option value="date">Newest</option>
                <option value="name">Name</option>
                <option value="size">Largest</option>
              </select>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--page-text-muted)" }} />
              </div>
            ) : items.length === 0 ? (
              <GlassCard className="p-16 text-center" >
                <ImageIcon className="w-10 h-10 mx-auto mb-3 opacity-40" style={{ color: "var(--page-text-muted)" }} />
                <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                  {search ? "Nothing matches that search." : "Drop files here, or use Upload."}
                </p>
              </GlassCard>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4">
                {items.map((item) => (
                  <GlassCard key={item.id} className="p-0 overflow-hidden group">
                    <button
                      onClick={() => setEditing(item)}
                      className="block w-full aspect-square"
                      style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
                    >
                      {item.kind === "image" && item.download_url ? (
                        <img
                          src={item.download_url}
                          alt={item.alt_text || item.filename}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Film className="w-8 h-8" style={{ color: "var(--page-text-muted)" }} />
                        </div>
                      )}
                    </button>
                    <div className="p-3 space-y-1.5">
                      <p className="text-xs truncate" style={{ color: "var(--page-text)" }}>
                        {item.filename}
                      </p>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px]" style={{ color: "var(--page-text-muted)" }}>
                          {formatBytes(item.size_bytes)}
                          {item.width ? ` · ${item.width}×${item.height}` : ""}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {item.used_in_posts > 0 && (
                            <Badge variant="info">{item.used_in_posts} in use</Badge>
                          )}
                          <button onClick={() => remove(item)}>
                            <Trash2 className="w-3.5 h-3.5 text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </button>
                        </div>
                      </div>
                      {item.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {item.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="text-[10px] px-1.5 py-0.5 rounded"
                              style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-muted)" }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}
          </div>
        </div>

        {dragging && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-purple-500/10 backdrop-blur-sm pointer-events-none">
            <div className="px-6 py-4 rounded-2xl bg-purple-500/20 border-2 border-dashed border-purple-400 text-purple-200 text-sm font-medium">
              Drop to upload
            </div>
          </div>
        )}
      </motion.div>

      <MediaDetailModal
        item={editing}
        folders={folders}
        onClose={() => setEditing(null)}
        onSaved={async () => {
          setEditing(null);
          await load();
        }}
      />
    </DashboardLayout>
  );
}

function MediaDetailModal({
  item,
  folders,
  onClose,
  onSaved,
}: {
  item: MediaItem | null;
  folders: MediaFolder[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [filename, setFilename] = useState("");
  const [altText, setAltText] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [folderId, setFolderId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!item) return;
    setFilename(item.filename);
    setAltText(item.alt_text ?? "");
    setTags(item.tags ?? []);
    setFolderId(item.folder_id);
    setTagDraft("");
  }, [item]);

  if (!item) return null;

  const save = async () => {
    setSaving(true);
    try {
      await updateMedia(item.id, { filename, alt_text: altText || null, tags });
      if (folderId !== item.folder_id) await moveMedia(item.id, folderId);
      showSuccess("Saved.");
      onSaved();
    } catch (err: any) {
      showError(errorDetail(err, "Could not save those changes."));
    }
    setSaving(false);
  };

  return (
    <Modal isOpen={!!item} onClose={onClose} title={item.filename} size="md">
      <div className="space-y-4">
        {item.kind === "image" && item.download_url && (
          <img
            src={item.download_url}
            alt={item.alt_text || item.filename}
            className="w-full max-h-64 object-contain rounded-xl"
            style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
          />
        )}

        <div className="grid grid-cols-2 gap-3 text-xs" style={{ color: "var(--page-text-muted)" }}>
          <span>{formatBytes(item.size_bytes)}</span>
          <span>{item.width ? `${item.width} × ${item.height}` : item.mime_type}</span>
          <span>Used in {item.used_in_posts} post(s)</span>
          <span>{new Date(item.created_at).toLocaleDateString()}</span>
        </div>

        <Input label="Filename" value={filename} onChange={(e) => setFilename(e.target.value)} />
        <Input
          label="Alt text"
          placeholder="Describes the image for screen readers"
          value={altText}
          onChange={(e) => setAltText(e.target.value)}
        />

        <div>
          <label className="text-sm font-medium block mb-1.5" style={{ color: "var(--page-text)" }}>
            Tags
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-1 rounded-lg flex items-center gap-1"
                style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text)" }}
              >
                {tag}
                <button onClick={() => setTags(tags.filter((t) => t !== tag))}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <Input
            placeholder="Add a tag and press Enter"
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              const value = tagDraft.trim();
              if (value && !tags.includes(value)) setTags([...tags, value]);
              setTagDraft("");
            }}
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5" style={{ color: "var(--page-text)" }}>
            Folder
          </label>
          <select
            value={folderId ?? ""}
            onChange={(e) => setFolderId(e.target.value || null)}
            className="w-full px-3 py-2 rounded-xl text-sm"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          >
            <option value="">Library root</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-2 pt-2" style={{ borderTop: "1px solid var(--surface-border)" }}>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={saving} onClick={save}>
            Save
          </Button>
        </div>
      </div>
    </Modal>
  );
}
