import { useCallback, useEffect, useState } from "react";
import { Check, Image as ImageIcon, Loader2, Search, Upload } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { showError } from "@/components/ui/Toast";
import {
  errorDetail,
  formatBytes,
  listMedia,
  uploadFile,
  type MediaItem,
} from "@/lib/media";
import { cn } from "@/lib/utils";

/**
 * Choose library files for a post.
 *
 * Returns the selected `MediaItem`s so the composer can send both `media_ids`
 * (which the backend records as usage) and the display URLs. Sending only URLs
 * is what the old flow did, and it is why nothing could tell whether a file was
 * still in use.
 */
export function MediaPicker({
  isOpen,
  onClose,
  onSelect,
  multiple = true,
  kind,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (items: MediaItem[]) => void;
  multiple?: boolean;
  kind?: "image" | "video";
}) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Record<string, MediaItem>>({});
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listMedia({ search, kind, per_page: 60 });
      setItems(result.items);
    } catch (err: any) {
      showError(errorDetail(err, "Could not load the media library."));
    }
    setLoading(false);
  }, [search, kind]);

  useEffect(() => {
    if (!isOpen) return;
    // Debounced so typing in the search box does not fire a request per keypress.
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [isOpen, load, search]);

  useEffect(() => {
    if (!isOpen) setSelected({});
  }, [isOpen]);

  const toggle = (item: MediaItem) => {
    setSelected((current) => {
      if (current[item.id]) {
        const { [item.id]: _removed, ...rest } = current;
        return rest;
      }
      return multiple ? { ...current, [item.id]: item } : { [item.id]: item };
    });
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const created = await uploadFile(file);
        setItems((current) => [created, ...current]);
        setSelected((current) =>
          multiple ? { ...current, [created.id]: created } : { [created.id]: created }
        );
      }
    } catch (err: any) {
      showError(errorDetail(err, "Upload failed."));
    }
    setUploading(false);
  };

  const chosen = Object.values(selected);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Media library" size="lg">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search by filename or tag…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              icon={<Search className="w-4 h-4" />}
            />
          </div>
          <label>
            <input
              type="file"
              multiple={multiple}
              accept={kind === "video" ? "video/*" : "image/*,video/*"}
              className="hidden"
              onChange={(e) => handleUpload(e.target.files)}
            />
            <span
              className="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm cursor-pointer"
              style={{
                backgroundColor: "var(--sidebar-hover-bg)",
                border: "1px solid var(--surface-border)",
                color: "var(--page-text)",
              }}
            >
              {uploading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              Upload
            </span>
          </label>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--page-text-muted)" }} />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16" style={{ color: "var(--page-text-muted)" }}>
            <ImageIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">
              {search ? "Nothing matches that search." : "The library is empty."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-h-[50vh] overflow-y-auto">
            {items.map((item) => {
              const isSelected = !!selected[item.id];
              return (
                <button
                  key={item.id}
                  onClick={() => toggle(item)}
                  className={cn(
                    "relative rounded-xl overflow-hidden aspect-square group",
                    isSelected && "ring-2 ring-purple-500"
                  )}
                  style={{
                    backgroundColor: "var(--sidebar-hover-bg)",
                    border: "1px solid var(--surface-border)",
                  }}
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
                      <ImageIcon className="w-6 h-6" style={{ color: "var(--page-text-muted)" }} />
                    </div>
                  )}
                  {isSelected && (
                    <span className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </span>
                  )}
                  <span className="absolute inset-x-0 bottom-0 px-2 py-1 text-[10px] truncate text-left bg-black/60 text-white">
                    {item.filename} · {formatBytes(item.size_bytes)}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <div
          className="flex items-center justify-between pt-3"
          style={{ borderTop: "1px solid var(--surface-border)" }}
        >
          <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
            {chosen.length} selected
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={chosen.length === 0}
              onClick={() => {
                onSelect(chosen);
                onClose();
              }}
            >
              Attach
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default MediaPicker;
