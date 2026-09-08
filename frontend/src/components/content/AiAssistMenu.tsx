/**
 * The "AI assist" menu on the content field.
 *
 * Two things it must get right, both about trust rather than features.
 *
 * **Undo.** An assist replaces text the author wrote. Replacing it with no way
 * back would make the menu something people are afraid to press, so the
 * previous text is kept and one click restores it. The undo survives further
 * typing — it is the author's text, not a transient.
 *
 * **Nothing fires on its own.** Every call is metered against the workspace's
 * monthly allowance, so there is no assist on blur, on debounce or on mount.
 * The author asks by name, every time.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Hash,
  Loader2,
  Maximize2,
  Minimize2,
  Sparkles,
  Undo2,
  Wand2,
} from "lucide-react";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { detailFrom } from "@/lib/scheduling";
import {
  assistOptions,
  runAssist,
  suggestHashtags,
  TONES,
  type AssistKind,
  type AssistOptions,
  type Tone,
} from "@/lib/aiAssist";

export function AiAssistMenu({
  accountId,
  content,
  platform,
  onApply,
  onHashtags,
  disabled,
}: {
  accountId: string | null;
  content: string;
  /** Shapes the hashtag count and keeps a rewrite inside the platform limit. */
  platform?: string | null;
  onApply: (next: string) => void;
  onHashtags?: (tags: string[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [toneOpen, setToneOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [options, setOptions] = useState<AssistOptions | null>(null);
  const [undoTo, setUndoTo] = useState<string | null>(null);
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accountId) return;
    assistOptions(accountId).then(setOptions).catch(() => {
      /* The menu still works; it just falls back to the built-in tone list. */
    });
  }, [accountId]);

  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) {
        setOpen(false);
        setToneOpen(false);
      }
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  const tooShort =
    content.trim().length < (options?.min_shorten_chars ?? 40);

  const apply = useCallback(
    async (kind: AssistKind, tone?: Tone) => {
      if (!accountId || !content.trim()) return;
      setBusy(kind + (tone ?? ""));
      const previous = content;
      try {
        const result = await runAssist(accountId, kind, {
          content,
          platform,
          ...(tone ? { tone } : {}),
        });
        setUndoTo(previous);
        onApply(result.result);
        setOpen(false);
        setToneOpen(false);
        const delta = result.result_length - result.original_length;
        showSuccess(
          `${kind === "change-tone" ? `Tone: ${tone}` : kind} · ` +
            `${delta >= 0 ? "+" : ""}${delta} characters · ${result.provider}`
        );
      } catch (err) {
        // The server leaves the author's text untouched on failure, so there
        // is nothing to roll back here — only something to say.
        showError(detailFrom(err, "The AI assist is unavailable right now."));
      } finally {
        setBusy(null);
      }
    },
    [accountId, content, platform, onApply]
  );

  const hashtags = useCallback(async () => {
    if (!accountId || !content.trim()) return;
    setBusy("hashtags");
    try {
      const result = await suggestHashtags(accountId, { content, platform });
      onHashtags?.(result.hashtags);
      setOpen(false);
      showSuccess(
        `${result.hashtags.length} hashtag${result.hashtags.length === 1 ? "" : "s"} for ${platform ?? "this post"}`
      );
    } catch (err) {
      showError(detailFrom(err, "Could not suggest hashtags."));
    } finally {
      setBusy(null);
    }
  }, [accountId, content, platform, onHashtags]);

  const tones = (options?.tones ?? [...TONES]) as Tone[];
  const idle = busy === null;

  return (
    <div className="flex items-center gap-1.5" ref={wrapper}>
      {undoTo !== null && (
        <button
          type="button"
          onClick={() => {
            onApply(undoTo);
            setUndoTo(null);
          }}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition-colors"
          style={{ color: "var(--page-text-secondary)", backgroundColor: "var(--sidebar-hover-bg)" }}
          title="Put back the text you had before the assist"
        >
          <Undo2 className="h-3.5 w-3.5" />
          Undo
        </button>
      )}

      <div className="relative">
        <button
          type="button"
          disabled={disabled || !accountId || !content.trim() || !idle}
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs transition-colors disabled:opacity-40"
          style={{ backgroundColor: "rgba(109,94,246,0.14)", color: "var(--page-heading)" }}
        >
          {idle ? <Sparkles className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          AI assist
          <ChevronDown className="h-3 w-3 opacity-60" />
        </button>

        {open && (
          <div
            className="absolute right-0 z-30 mt-1 w-60 overflow-hidden rounded-xl py-1 shadow-xl"
            style={{
              backgroundColor: "var(--surface-bg)",
              border: "1px solid var(--surface-border)",
            }}
          >
            <Item icon={<Wand2 className="h-3.5 w-3.5" />} label="Rewrite"
                  hint="Clearer, same length" busy={busy === "rewrite"}
                  onClick={() => apply("rewrite")} />
            <Item icon={<Minimize2 className="h-3.5 w-3.5" />} label="Shorten"
                  hint={tooShort ? `Needs ${options?.min_shorten_chars ?? 40}+ characters` : "Tighter"}
                  disabled={tooShort} busy={busy === "shorten"}
                  onClick={() => apply("shorten")} />
            <Item icon={<Maximize2 className="h-3.5 w-3.5" />} label="Expand"
                  hint="More detail" busy={busy === "expand"}
                  onClick={() => apply("expand")} />
            <Item icon={<Hash className="h-3.5 w-3.5" />} label="Suggest hashtags"
                  hint={
                    platform && options?.hashtag_counts?.[platform]
                      ? `${options.hashtag_counts[platform]} for ${platform}`
                      : "Based on the post"
                  }
                  busy={busy === "hashtags"} onClick={hashtags} />

            <div className="my-1 h-px" style={{ backgroundColor: "var(--surface-border)" }} />

            <button
              type="button"
              onClick={() => setToneOpen((v) => !v)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:opacity-80"
              style={{ color: "var(--page-text)" }}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Change tone
              <ChevronDown className={cn("ml-auto h-3 w-3 transition-transform", toneOpen && "rotate-180")} />
            </button>
            {toneOpen && (
              <div className="max-h-52 overflow-auto pb-1">
                {tones.map((tone) => (
                  <button
                    key={tone}
                    type="button"
                    disabled={busy !== null}
                    onClick={() => apply("change-tone", tone)}
                    className="flex w-full items-center gap-2 py-1.5 pl-9 pr-3 text-left text-xs capitalize transition-colors hover:opacity-80 disabled:opacity-40"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    {busy === "change-tone" + tone && <Loader2 className="h-3 w-3 animate-spin" />}
                    {tone}
                  </button>
                ))}
              </div>
            )}

            <p className="px-3 pb-1 pt-2 text-[10px]" style={{ color: "var(--page-text-muted)" }}>
              Each assist uses one AI request from your monthly allowance.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Item({
  icon, label, hint, onClick, busy, disabled,
}: {
  icon: React.ReactNode; label: string; hint?: string;
  onClick: () => void; busy?: boolean; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      onClick={onClick}
      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:opacity-80 disabled:opacity-40"
      style={{ color: "var(--page-text)" }}
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      <span>{label}</span>
      {hint && (
        <span className="ml-auto text-[10px]" style={{ color: "var(--page-text-muted)" }}>
          {hint}
        </span>
      )}
    </button>
  );
}

export default AiAssistMenu;
