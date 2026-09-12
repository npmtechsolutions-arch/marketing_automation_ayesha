/**
 * Turning a failed request into a sentence that names the actual problem.
 *
 * Written after a real support round-trip: signing up showed "Registration
 * failed. Please try again." and Google sign-in showed "Network Error", when
 * what had actually happened was that the frontend was calling another
 * project's API on port 8000. The browser blocked the cross-origin response,
 * so axios had **no response object at all** — and every caller in the app
 * reads `err.response.data.detail`, which does not exist in that case, so they
 * all fell through to a generic string. The one fact that would have explained
 * it in a second — "could not reach the API at http://localhost:8000/api/v1" —
 * was the one thing nothing printed.
 *
 * So this distinguishes the cases a person can act on differently:
 *
 * - the request never got an answer (backend down, wrong port, CORS);
 * - the server answered but is not this API (a 404 with no `detail`);
 * - the server refused with a reason (`detail`), including rate limits;
 * - anything else.
 */

/** The API base the app is actually calling, for error messages. */
export function apiBaseLabel(base: string): string {
  if (base.startsWith("http")) return base;
  if (typeof window !== "undefined") return `${window.location.origin}${base}`;
  return base;
}

interface AxiosLike {
  response?: { status?: number; data?: { detail?: unknown } };
  message?: string;
  code?: string;
}

/**
 * A message that names the cause.
 *
 * `fallback` is used only when the server answered with something this cannot
 * interpret — never for an unreachable API, which has its own sentence.
 */
export function apiErrorMessage(
  error: unknown,
  fallback: string,
  options: { apiBase?: string } = {}
): string {
  const err = (error ?? {}) as AxiosLike;
  const base = apiBaseLabel(options.apiBase ?? "/api/v1");

  // No response at all: the request did not reach an API that would answer us.
  // This is the case that used to surface as "Network Error".
  if (!err.response) {
    if (err.code === "ECONNABORTED") {
      return `The API at ${base} did not answer in time. It may be starting up.`;
    }
    return (
      `Could not reach the MarketEngine API at ${base}. ` +
      `Check the backend is running, and that it is the one this app expects ` +
      `— another service answering on that port fails exactly this way.`
    );
  }

  const status = err.response.status;
  const detail = err.response.data?.detail;
  const hasDetail = typeof detail === "string" && detail.trim().length > 0;

  // Rate limiting deserves its own sentence: "try again" is actively wrong
  // advice when the server means "not for another hour".
  if (status === 429) {
    return hasDetail
      ? (detail as string)
      : "Too many attempts from this network. Wait a little and try again.";
  }

  // A 404 with no usable detail on an endpoint the app knows exists means the
  // base URL is pointed at something that is not this API.
  if (status === 404 && (!hasDetail || detail === "Not Found")) {
    return (
      `The API at ${base} does not recognise this request (404). ` +
      `That usually means the app is pointed at the wrong backend.`
    );
  }

  if (hasDetail) return detail as string;

  // Pydantic validation errors arrive as a list of objects, which would
  // otherwise render as "[object Object]".
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    if (first?.msg) {
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
      return field ? `${String(field)}: ${first.msg}` : first.msg;
    }
  }

  if (status && status >= 500) {
    return `The server failed while handling that (${status}). ${fallback}`;
  }
  return fallback;
}
