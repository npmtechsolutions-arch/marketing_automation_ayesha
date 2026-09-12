import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CornerDownRight,
  Link2,
  Loader2,
  MessageSquare,
  RotateCcw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import PlatformIcon from "@/components/shared/PlatformIcon";
import { showError, showSuccess } from "@/components/ui/Toast";
import {
  countCharacters,
  deleteVariant,
  listVariants,
  saveVariant,
  validatePost,
  type PostValidation,
  type PostVariant,
} from "@/lib/variants";
import { cn } from "@/lib/utils";

const ICON_PLATFORMS = ["facebook", "instagram", "linkedin", "tiktok", "twitter", "youtube"] as const;
type IconPlatform = (typeof ICON_PLATFORMS)[number];
const isKnownPlatform = (slug: string): slug is IconPlatform =>
  (ICON_PLATFORMS as readonly string[]).includes(slug);

const PLATFORM_LABEL: Record<string, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  linkedin: "LinkedIn",
  twitter: "X",
  youtube: "YouTube",
};

const errorDetail = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
};

/**
 * Platform tabs over one post.
 *
 * "Master" is the content the author writes once; each platform tab shows
 * either that content (inherited) or its own override. The distinction is
 * shown explicitly rather than implied, because an author who cannot tell
 * which they are editing will eventually edit the wrong one.
 */
export function PlatformVariants({
  postId,
  masterContent,
  hashtags,
  platforms,
  onChanged,
}: {
  postId: string;
  masterContent: string;
  hashtags: string[];
  /** Slugs of the platforms this post targets. */
  platforms: string[];
  onChanged?: () => void;
}) {
  const [active, setActive] = useState<string>("master");
  const [variants, setVariants] = useState<Record<string, PostVariant>>({});
  const [validation, setValidation] = useState<PostValidation | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [firstComment, setFirstComment] = useState<string>("");
  const [linkUrl, setLinkUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, result] = await Promise.all([
        listVariants(postId),
        validatePost(postId).catch(() => null),
      ]);
      setVariants(Object.fromEntries(rows.map((v) => [v.platform_slug, v])));
      if (result) setValidation(result);
    } catch (err: any) {
      showError(errorDetail(err, "Could not load per-platform versions."));
    }
    setLoading(false);
  }, [postId]);

  useEffect(() => {
    load();
  }, [load]);

  // Switching tabs loads that platform's override, or the master it inherits.
  useEffect(() => {
    if (active === "master") return;
    const variant = variants[active];
    setDraft(variant?.content ?? masterContent);
    setFirstComment(variant?.first_comment ?? "");
    setLinkUrl(variant?.link_url ?? "");
  }, [active, variants, masterContent]);

  const validationFor = useMemo(() => {
    const map: Record<string, PostValidation["platforms"][number]> = {};
    for (const p of validation?.platforms ?? []) map[p.platform] = p;
    return map;
  }, [validation]);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await saveVariant(postId, active, {
        // Sending the master text unchanged would freeze this platform at
        // today's copy; null keeps it following the master.
        content: draft === masterContent ? null : draft,
        first_comment: firstComment.trim() || null,
        link_url: linkUrl.trim() || null,
      });
      setVariants((current) => ({ ...current, [active]: updated }));
      showSuccess(`Saved the ${PLATFORM_LABEL[active] ?? active} version.`);
      setValidation(await validatePost(postId));
      onChanged?.();
    } catch (err: any) {
      showError(errorDetail(err, "Could not save that version."));
    }
    setSaving(false);
  };

  const reset = async () => {
    if (!window.confirm(`Drop the ${PLATFORM_LABEL[active] ?? active} version and follow the master post?`))
      return;
    try {
      await deleteVariant(postId, active);
      setVariants((current) => {
        const { [active]: _dropped, ...rest } = current;
        return rest;
      });
      setDraft(masterContent);
      setFirstComment("");
      setLinkUrl("");
      setValidation(await validatePost(postId));
      onChanged?.();
    } catch (err: any) {
      showError(errorDetail(err, "Could not reset that version."));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs" style={{ color: "var(--page-text-muted)" }}>
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading per-platform versions…
      </div>
    );
  }
  if (platforms.length === 0) return null;

  const current = validationFor[active];
  const variant = variants[active];
  const isOverridden = !!variant?.overrides.length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        <TabButton
          label="Master"
          active={active === "master"}
          onClick={() => setActive("master")}
        />
        {platforms.map((slug) => {
          const result = validationFor[slug];
          return (
            <TabButton
              key={slug}
              label={PLATFORM_LABEL[slug] ?? slug}
              slug={slug}
              active={active === slug}
              customised={!!variants[slug]?.overrides.length}
              status={result ? (result.ok ? "ok" : "error") : undefined}
              onClick={() => setActive(slug)}
            />
          );
        })}
      </div>

      {active === "master" ? (
        <div
          className="rounded-xl p-3 text-xs"
          style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-secondary)" }}
        >
          Every platform publishes this unless you customise its tab. The counters
          below show how it measures against each one.
          <div className="mt-3 space-y-1.5">
            {platforms.map((slug) => {
              const result = validationFor[slug];
              if (!result) return null;
              return (
                <CharacterMeter
                  key={slug}
                  slug={slug}
                  count={
                    variants[slug]?.content != null
                      ? countCharacters(variants[slug].content ?? "", [])
                      : countCharacters(masterContent, hashtags)
                  }
                  limit={result.character_limit}
                  inherited={!variants[slug]?.overrides.length}
                />
              );
            })}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs flex items-center gap-1.5" style={{ color: "var(--page-text-secondary)" }}>
              {isOverridden ? (
                <>
                  <CornerDownRight className="w-3.5 h-3.5 text-purple-400" />
                  Customised for {PLATFORM_LABEL[active] ?? active}
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  Inherited from the master post
                </>
              )}
            </span>
            {isOverridden && (
              <button
                onClick={reset}
                className="text-xs flex items-center gap-1 hover:opacity-80"
                style={{ color: "var(--page-text-muted)" }}
              >
                <RotateCcw className="w-3 h-3" />
                Follow master
              </button>
            )}
          </div>

          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={6}
            className="w-full rounded-xl px-3 py-2.5 text-sm outline-none resize-y"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />

          {current && (
            <CharacterMeter
              slug={active}
              count={countCharacters(draft, isOverridden ? [] : hashtags)}
              limit={current.character_limit}
              inherited={false}
            />
          )}

          <Input
            label="First comment"
            placeholder="Posted as a reply right after publishing"
            icon={<MessageSquare className="w-4 h-4" />}
            value={firstComment}
            onChange={(e) => setFirstComment(e.target.value)}
          />
          <Input
            label="Link"
            placeholder="https://…"
            icon={<Link2 className="w-4 h-4" />}
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
          />

          <div className="flex justify-end">
            <Button variant="primary" loading={saving} onClick={save}>
              Save {PLATFORM_LABEL[active] ?? active} version
            </Button>
          </div>
        </div>
      )}

      {/* Errors are shown per platform rather than as one list: an author
          needs to know which tab to open, not just that something is wrong. */}
      {current && current.errors.length > 0 && (
        <ul className="space-y-1.5">
          {current.errors.map((issue, i) => (
            <li
              key={i}
              className={cn(
                "text-xs flex items-start gap-2 rounded-lg p-2.5",
                issue.severity === "error"
                  ? "bg-red-500/10 text-red-300"
                  : "bg-amber-500/10 text-amber-300"
              )}
            >
              {issue.severity === "error" ? (
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              )}
              <span>
                <span className="opacity-70">{issue.field}: </span>
                {issue.message}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TabButton({
  label,
  slug,
  active,
  customised,
  status,
  onClick,
}: {
  label: string;
  slug?: string;
  active: boolean;
  customised?: boolean;
  status?: "ok" | "error";
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors",
        active && "bg-purple-500/15 text-purple-300"
      )}
      style={active ? undefined : { color: "var(--page-text-secondary)" }}
    >
      {slug && isKnownPlatform(slug) && <PlatformIcon platform={slug} size="sm" />}
      {label}
      {customised && <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />}
      {status === "error" && <AlertCircle className="w-3 h-3 text-red-400" />}
    </button>
  );
}

function CharacterMeter({
  slug,
  count,
  limit,
  inherited,
}: {
  slug: string;
  count: number;
  limit: number | null;
  inherited: boolean;
}) {
  const over = limit != null && count > limit;
  const near = limit != null && !over && count > limit * 0.9;
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="flex items-center gap-1.5" style={{ color: "var(--page-text-muted)" }}>
        {isKnownPlatform(slug) && <PlatformIcon platform={slug} size="sm" />}
        {PLATFORM_LABEL[slug] ?? slug}
        {inherited && <span className="opacity-60">(inherited)</span>}
      </span>
      <span
        className={cn(
          "tabular-nums",
          over && "text-red-400 font-medium",
          near && "text-amber-400"
        )}
        style={over || near ? undefined : { color: "var(--page-text-muted)" }}
      >
        {count.toLocaleString()}
        {limit != null ? ` / ${limit.toLocaleString()}` : ""}
        {over ? ` (${(count - limit!).toLocaleString()} over)` : ""}
      </span>
    </div>
  );
}

export default PlatformVariants;
