/**
 * Central authenticated API helpers for Forma APA.
 * Retrieves the current Supabase session access token — never duplicates JWTs.
 */
import { supabase } from "../supabaseClient";

export class AuthSessionError extends Error {
  constructor(message = "Your session has expired. Please sign in again.") {
    super(message);
    this.name = "AuthSessionError";
  }
}

export async function getAccessToken() {
  const {
    data: { session },
    error,
  } = await supabase.auth.getSession();

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

function filenameFromContentDisposition(headerValue) {
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
  return plainMatch?.[1] || null;
}

/**
 * Download a protected DOCX through the app API (Bearer + optional token query).
 * Uses a temporary object URL — never exposes private Blob URLs.
 */
export async function downloadAuthenticatedFile(url, fallbackFilename = "formatted.docx") {
  const response = await authenticatedFetch(url, { method: "GET" });

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

  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // Revoke shortly after click so the download can start.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }
}
