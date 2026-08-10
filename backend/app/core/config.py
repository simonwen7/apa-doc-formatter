"""Environment and runtime configuration for Forma APA backend."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
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
DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS = int(
    os.getenv("DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS") or "3600"
)  # 1 hour default
LOCAL_DEV_DOWNLOAD_SECRET = "forma-apa-local-dev-download-secret-only"

# Fixed-document retention (hours). Controlled beta default: 24h.
DOCUMENT_RETENTION_HOURS = int(os.getenv("DOCUMENT_RETENTION_HOURS") or "24")

# Protected cleanup job (cron). Required in production to call cleanup endpoint.
CLEANUP_JOB_SECRET = os.getenv("CLEANUP_JOB_SECRET")

# CORS: comma-separated origins. Localhost always allowed for development.
_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (os.getenv("CORS_ALLOWED_ORIGINS") or _DEFAULT_CORS).split(",")
    if origin.strip()
]

# Fixed-document namespace prefix — cleanup must never delete outside this.
FIXED_BLOB_NAMESPACE = "fixed/"


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
