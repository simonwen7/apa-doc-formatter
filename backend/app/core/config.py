"""Environment and runtime configuration for Forma APA backend."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
# backend/app -> backend/
_BACKEND_ROOT = BASE_DIR.parent
_ENV_FILE = _BACKEND_ROOT / ".env"

# Load local backend/.env for development without exporting secrets into the shell.
# Does not override already-set process environment (Vercel/prod inject wins).
try:
    from dotenv import load_dotenv

    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    # Production may omit python-dotenv if platform injects env vars.
    pass

TEMPLATES_DIR = BASE_DIR / "templates"

# Vercel sets VERCEL=1 in production/preview function runtimes.
IS_VERCEL = os.getenv("VERCEL") == "1"
APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
IS_PRODUCTION = IS_VERCEL or APP_ENV in {"production", "prod", "preview"}

# Runtime workspace for python-docx temp reads/writes.
# On Vercel the deployment FS is read-only except /tmp.
if IS_VERCEL:
    RUNTIME_DIR = Path("/tmp/docformatter")
else:
    RUNTIME_DIR = BASE_DIR.parent / "storage"

UPLOADS_DIR = RUNTIME_DIR / "uploads"
FIXED_DIR = RUNTIME_DIR / "fixed"

# Private Vercel Blob is required when fixed files must survive across
# separate serverless invocations (fix -> download).
# On Vercel, prefer OIDC (VERCEL_OIDC_TOKEN + BLOB_STORE_ID).
# BLOB_READ_WRITE_TOKEN remains an optional fallback when explicitly set.
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
BLOB_STORE_ID = os.getenv("BLOB_STORE_ID") or os.getenv("VERCEL_BLOB_STORE_ID")
USE_BLOB_STORAGE = IS_VERCEL

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# Supabase Auth (server verification). Prefer publishable/anon key — never a
# VITE_ frontend secret duplication of service-role keys.
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or ""
).strip()

# HMAC download tokens (defense in depth; ownership is primary).
# Production MUST set DOCUMENT_DOWNLOAD_SECRET (no insecure fallback).
DOCUMENT_DOWNLOAD_SECRET = os.getenv("DOCUMENT_DOWNLOAD_SECRET")
LOCAL_DEV_DOWNLOAD_SECRET = "forma-apa-local-dev-download-secret-only"

# Protected cleanup job.
# Official Vercel Cron sends: Authorization: Bearer <CRON_SECRET>
# Manual ops may also use X-Cleanup-Secret with CLEANUP_JOB_SECRET.
CRON_SECRET = os.getenv("CRON_SECRET")
CLEANUP_JOB_SECRET = os.getenv("CLEANUP_JOB_SECRET")

# Fixed-document namespace prefix — cleanup must never delete outside this.
FIXED_BLOB_NAMESPACE = "fixed/"

_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"
_ORIGIN_RE = re.compile(r"^https?://[^/\s]+$", re.IGNORECASE)


def parse_positive_int(name: str, raw: str | None, *, default: int) -> int:
    """Parse a positive integer env value. Raises ValueError with a safe message."""
    if raw is None or str(raw).strip() == "":
        value = default
    else:
        try:
            value = int(str(raw).strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be a positive integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def parse_cors_origins(raw: str | None = None) -> list[str]:
    """
    Parse CORS origins.

    - Rejects wildcard '*'
    - Accepts only absolute http(s) origins without paths
    - Always includes local Vite defaults
    - Deduplicates while preserving order
    """
    source = raw if raw is not None else os.getenv("CORS_ALLOWED_ORIGINS")
    combined = f"{_DEFAULT_CORS},{source or ''}"
    origins: list[str] = []
    seen: set[str] = set()
    for part in combined.split(","):
        origin = part.strip()
        if not origin:
            continue
        if origin == "*":
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must not include '*' for authenticated APIs."
            )
        if not _ORIGIN_RE.fullmatch(origin):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS entries must be absolute http(s) origins "
                "without paths (example shape: https://example.com)."
            )
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("CORS_ALLOWED_ORIGINS contains an invalid origin.")
        if origin in seen:
            continue
        seen.add(origin)
        origins.append(origin)
    if not origins:
        raise ValueError("CORS_ALLOWED_ORIGINS resolved to an empty list.")
    return origins


def download_token_ttl_seconds() -> int:
    return parse_positive_int(
        "DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS",
        os.getenv("DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS"),
        default=3600,
    )


def document_retention_hours() -> int:
    return parse_positive_int(
        "DOCUMENT_RETENTION_HOURS",
        os.getenv("DOCUMENT_RETENTION_HOURS"),
        default=24,
    )


# Eager defaults for import-time convenience; helpers re-read env when needed.
DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS = download_token_ttl_seconds()
DOCUMENT_RETENTION_HOURS = document_retention_hours()
CORS_ALLOWED_ORIGINS = parse_cors_origins()


def ensure_runtime_dirs() -> None:
    """Create local/runtime directories lazily (never at import time)."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    FIXED_DIR.mkdir(parents=True, exist_ok=True)


def resolve_download_secret() -> bytes:
    """
    Resolve the HMAC signing secret.

    Production/preview (IS_PRODUCTION): DOCUMENT_DOWNLOAD_SECRET is required
    and must be at least 32 characters. No hardcoded or Blob-token fallback.

    Local development: DOCUMENT_DOWNLOAD_SECRET if set, otherwise the
    documented local-only constant.
    """
    explicit = (DOCUMENT_DOWNLOAD_SECRET or "").strip()
    if IS_PRODUCTION:
        if not explicit:
            raise RuntimeError(
                "DOCUMENT_DOWNLOAD_SECRET must be set in production/preview."
            )
        if len(explicit) < 32:
            raise RuntimeError(
                "DOCUMENT_DOWNLOAD_SECRET must be at least 32 characters."
            )
        return explicit.encode("utf-8")

    if explicit:
        return explicit.encode("utf-8")
    return LOCAL_DEV_DOWNLOAD_SECRET.encode("utf-8")


def resolve_cleanup_secrets() -> tuple[str, ...]:
    """Accepted cleanup authenticator values (CRON_SECRET and/or CLEANUP_JOB_SECRET)."""
    values = []
    for candidate in (CRON_SECRET, CLEANUP_JOB_SECRET):
        text = (candidate or "").strip()
        if text and text not in values:
            values.append(text)
    return tuple(values)
