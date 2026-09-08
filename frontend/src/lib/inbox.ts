/**
 * The unified inbox.
 *
 * `capabilities` matters as much as the threads do: a platform with no message
 * API returns nothing, which is indistinguishable from a quiet inbox unless the
 * UI knows the difference and says so.
 */
import api from "@/lib/api";

export type ThreadType = "comment" | "dm" | "mention";
export type ThreadStatus = "open" | "resolved";
export type Direction = "inbound" | "outbound" | "internal";

export interface Thread {
  id: string;
  type: ThreadType;
  platform: string | null;
  social_account_id: string;
  participant: string;
  participant_handle: string | null;
  permalink: string | null;
  status: ThreadStatus;
  assigned_to: string | null;
  tags: string[];
  unread_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
}

export interface Message {
  id: string;
  direction: Direction;
  author: string;
  author_handle: string | null;
  author_user_id: string | null;
  body: string;
  media: unknown[];
  created_at: string;
}

export interface ThreadDetail extends Thread {
  messages: Message[];
}

export interface ConnectionCapability {
  social_account_id: string;
  platform: string;
  account_name: string;
  supports: Record<ThreadType, boolean>;
}

export interface ThreadFilters {
  platform?: string;
  status?: ThreadStatus;
  type?: ThreadType;
  assigned_to?: string;
  unassigned?: boolean;
  tag?: string;
}

const base = (accountId: string) => `/accounts/${accountId}/inbox`;

export const inboxApi = {
  list: (accountId: string, filters: ThreadFilters = {}) => {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "" && value !== false) {
        query.set(key, String(value));
      }
    });
    return api
      .get<{ threads: Thread[]; counts: Record<string, number> }>(
        `${base(accountId)}/?${query}`
      )
      .then((r) => r.data);
  },

  capabilities: (accountId: string) =>
    api
      .get<{ connections: ConnectionCapability[] }>(`${base(accountId)}/capabilities`)
      .then((r) => r.data.connections),

  thread: (accountId: string, threadId: string) =>
    api.get<ThreadDetail>(`${base(accountId)}/${threadId}`).then((r) => r.data),

  reply: (accountId: string, threadId: string, body: string) =>
    api.post<Message>(`${base(accountId)}/${threadId}/reply`, { body }).then((r) => r.data),

  note: (accountId: string, threadId: string, body: string) =>
    api.post<Message>(`${base(accountId)}/${threadId}/note`, { body }).then((r) => r.data),

  assign: (accountId: string, threadId: string, assigned_to: string | null) =>
    api.put<Thread>(`${base(accountId)}/${threadId}/assign`, { assigned_to }).then((r) => r.data),

  setTags: (accountId: string, threadId: string, tags: string[]) =>
    api.put<Thread>(`${base(accountId)}/${threadId}/tags`, { tags }).then((r) => r.data),

  setStatus: (accountId: string, threadId: string, status: ThreadStatus) =>
    api.put<Thread>(`${base(accountId)}/${threadId}/status`, { status }).then((r) => r.data),

  syncNow: (accountId: string) =>
    api
      .post<{ new_messages: number; unsupported: string[]; errors: string[] }>(
        `${base(accountId)}/sync`
      )
      .then((r) => r.data),
};

/** Whether this thread can be answered from the inbox at all. */
export function canReply(thread: Pick<Thread, "type">): boolean {
  // A mention lives on someone else's post; replying means composing a new
  // public post, which belongs to the composer rather than here.
  return thread.type !== "mention";
}

export const TYPE_LABELS: Record<ThreadType, string> = {
  comment: "Comment",
  dm: "Message",
  mention: "Mention",
};
