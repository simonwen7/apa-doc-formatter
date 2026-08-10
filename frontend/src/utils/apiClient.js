/**
 * Central authenticated API helpers for Forma APA.
 * Retrieves the current Supabase session access token — never duplicates JWTs.
 */

export class AuthSessionError extends Error {
  constructor(message = "Your session has expired. Please sign in again.") {
    super(message);
    this.name = "AuthSessionError";
  }
}

/** @type {null | (() => Promise<{ data: { session: { access_token?: string } | null }, error: Error | null }>)} */
let getSessionOverride = null;

/** Test-only hook — do not use in production UI. */
export function __setGetSessionForTests(fn) {
  getSessionOverride = fn;
}

async function readSession() {
  if (getSessionOverride) {
    return getSessionOverride();
  }
  const { supabase } = await import("../supabaseClient.js");
  return supabase.auth.getSession();
}

export async function getAccessToken() {
  const {
    data: { session },
    error,
  } = await readSession();

  if (error || !session?.access_token) {
    throw new AuthSessionError();
  }

  return session.access_token;
}

export async function getAuthHeaders(extra = {}) {
  const token = await getAccessToken();
  return {
    ...extra,
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Authenticated fetch wrapper. Does not set Content-Type for FormData bodies.
 */
export async function authenticatedFetch(url, options = {}) {
  const headers = await getAuthHeaders(options.headers || {});
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new AuthSessionError();
  }

  return response;
}

export function filenameFromContentDisposition(headerValue) {
  if (!headerValue) return null;
  const utfMatch = /filename\*=UTF-8''([^;]+)/i.exec(headerValue);
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1]);
    } catch {
      return utfMatch[1];
    }
  }
  const plainMatch = /filename="?([^";]+)"?/i.exec(headerValue);
  const name = plainMatch?.[1] || null;
  if (!name) return null;
  // Basename only; strip directories / separators / traversal fragments.
  const safe = name
    .split(/[/\\]/)
    .pop()
    .replace(/\.\./g, "")
    .trim();
  return safe || null;
}

/**
 * Download a protected DOCX through the app API (Bearer + optional token query).
 * Uses a temporary object URL — never exposes private Blob URLs.
 */
export async function downloadAuthenticatedFile(
  url,
  fallbackFilename = "formatted.docx",
  hooks = {}
) {
  const createObjectURL = hooks.createObjectURL || URL.createObjectURL.bind(URL);
  const revokeObjectURL = hooks.revokeObjectURL || URL.revokeObjectURL.bind(URL);
  const fetchImpl = hooks.fetchImpl || authenticatedFetch;

  let objectUrl = null;
  try {
    const response = await fetchImpl(url, { method: "GET" });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail =
        typeof data?.detail === "string"
          ? data.detail
          : `Download failed with status ${response.status}.`;
      throw new Error(detail);
    }

    const blob = await response.blob();
    const filename =
      filenameFromContentDisposition(response.headers.get("Content-Disposition")) ||
      fallbackFilename;

    objectUrl = createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return filename;
  } finally {
    if (objectUrl) {
      const revoke = () => revokeObjectURL(objectUrl);
      if (hooks.revokeImmediately) {
        revoke();
      } else if (typeof window !== "undefined" && window.setTimeout) {
        window.setTimeout(revoke, 1000);
      } else {
        revoke();
      }
    }
  }
}
