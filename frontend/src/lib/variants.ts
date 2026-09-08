import api, { getAccountId } from "@/lib/api";

/** Mirrors app/schemas/post_variant.py */
export interface PostVariant {
  id: string;
  post_id: string;
  platform_slug: string;
  content: string | null;
  media: string[];
  link_url: string | null;
  alt_texts: Record<string, string>;
  thumbnail_media_id: string | null;
  first_comment: string | null;
  /** Which fields this variant overrides; the rest inherit from the master. */
  overrides: string[];
}

export interface ValidationErrorItem {
  platform: string;
  field: string;
  message: string;
  severity: "error" | "warning";
}

export interface PlatformValidation {
  platform: string;
  accounts: string[];
  ok: boolean;
  character_count: number;
  character_limit: number | null;
  media_count: number;
  errors: ValidationErrorItem[];
}

export interface PostValidation {
  valid: boolean;
  platforms: PlatformValidation[];
  errors: ValidationErrorItem[];
}

/** Mirrors app/schemas/social_account.py::SocialAccountCapabilities */
export interface Capabilities {
  social_account_id: string;
  platform_slug: string;
  platform_name: string;
  supports_images: boolean;
  supports_video: boolean;
  supports_carousel: boolean;
  supports_link_posts: boolean;
  supports_comments_api: boolean;
  supports_dm_api: boolean;
  max_chars: number | null;
  max_images: number;
  max_video_seconds: number | null;
  max_video_bytes: number | null;
}

async function postBase(postId: string): Promise<string> {
  const accountId = await getAccountId();
  if (!accountId) throw new Error("No workspace selected");
  return `/accounts/${accountId}/posts/${postId}`;
}

export async function listVariants(postId: string): Promise<PostVariant[]> {
  const res: any = await api.get(`${await postBase(postId)}/variants`);
  return res.data ?? res;
}

export async function saveVariant(
  postId: string,
  slug: string,
  changes: Partial<{
    content: string | null;
    media: string[] | null;
    link_url: string | null;
    alt_texts: Record<string, string> | null;
    thumbnail_media_id: string | null;
    first_comment: string | null;
  }>
): Promise<PostVariant> {
  const res: any = await api.put(`${await postBase(postId)}/variants/${slug}`, changes);
  return res.data ?? res;
}

export async function deleteVariant(postId: string, slug: string): Promise<void> {
  await api.delete(`${await postBase(postId)}/variants/${slug}`);
}

export async function validatePost(postId: string): Promise<PostValidation> {
  const res: any = await api.post(`${await postBase(postId)}/validate`, {});
  return res.data ?? res;
}

export async function fetchCapabilities(
  socialAccountId: string
): Promise<Capabilities> {
  const accountId = await getAccountId();
  const res: any = await api.get(
    `/accounts/${accountId}/social-accounts/${socialAccountId}/capabilities`
  );
  return res.data ?? res;
}

/**
 * Characters as the platform counts them.
 *
 * Mirrors `_plain_length` in app/services/post_validation.py: hashtags live in
 * their own field but publish in the body, so a counter that ignores them
 * under-reports and the author finds out at publish time. Like the server, this
 * does not model X's URL shortening — counting links in full errs toward
 * warning about a post that would have fit, rather than accepting one that
 * will not.
 */
export function countCharacters(content: string, hashtags: string[]): number {
  let body = content || "";
  for (const tag of hashtags || []) {
    const token = tag.startsWith("#") ? tag : `#${tag}`;
    if (!body.includes(token)) body += ` ${token}`;
  }
  return body.length;
}
