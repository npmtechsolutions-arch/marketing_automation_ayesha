/**
 * The inline composer assists.
 *
 * Each call is metered against the workspace's monthly AI allowance, which is
 * why the UI must not fire them speculatively — no assist on blur, on debounce
 * or on mount. Every request is something the author asked for by name.
 */
import api from "@/lib/api";

export type AssistKind = "rewrite" | "shorten" | "expand" | "change-tone";

export const TONES = [
  "professional",
  "casual",
  "friendly",
  "witty",
  "authoritative",
  "inspirational",
  "urgent",
  "empathetic",
] as const;
export type Tone = (typeof TONES)[number];

export interface AssistResult {
  result: string;
  provider: string;
  model: string;
  generation_id: string;
  original_length: number;
  result_length: number;
}

export interface HashtagResult {
  hashtags: string[];
  provider: string;
  model: string;
  generation_id: string;
}

export interface AssistOptions {
  tones: string[];
  providers: string[];
  hashtag_counts: Record<string, number>;
  min_shorten_chars: number;
}

const base = (accountId: string) => `/accounts/${accountId}/ai`;

export function assistOptions(accountId: string): Promise<AssistOptions> {
  return api.get<AssistOptions>(`${base(accountId)}/assist-options`).then((r) => r.data);
}

export function runAssist(
  accountId: string,
  kind: AssistKind,
  body: { content: string; platform?: string | null; tone?: Tone; provider?: string }
): Promise<AssistResult> {
  return api.post<AssistResult>(`${base(accountId)}/${kind}`, body).then((r) => r.data);
}

export function suggestHashtags(
  accountId: string,
  body: { content: string; platform?: string | null; provider?: string }
): Promise<HashtagResult> {
  return api
    .post<HashtagResult>(`${base(accountId)}/suggest-hashtags`, body)
    .then((r) => r.data);
}
