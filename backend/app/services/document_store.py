"""Persistent document storage for analyze/fix/download.

Why this exists
---------------
- analyze: upload is processed in the same request; no cross-request persistence needed.
- fix: uploads again, writes a fixed DOCX, returns /documents/download/{id}.
- download: a SEPARATE HTTP request that must find that fixed DOCX.

On Vercel serverless, /tmp is not reliable across invocations. Fixed documents
are therefore stored in a private Vercel Blob store in production, while
python-docx still reads/writes temporary files under /tmp/docformatter.

Locally, files remain under backend/storage for the existing workflow.

Authentication on Vercel
------------------------
Private Blob stores default to OIDC (VERCEL_OIDC_TOKEN + BLOB_STORE_ID).
The current Python vercel.blob SDK still resolves only BLOB_READ_WRITE_TOKEN
internally, so on Vercel we authenticate with OIDC via the Blob HTTP API.
BLOB_READ_WRITE_TOKEN remains an optional fallback when explicitly provided.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException

from app.core.config import (
    DOCX_MEDIA_TYPE,
    FIXED_DIR,
    UPLOADS_DIR,
    USE_BLOB_STORAGE,
    ensure_runtime_dirs,
)

logger = logging.getLogger(__name__)

BLOB_API_URL = os.getenv("VERCEL_BLOB_API_URL") or "https://vercel.com/api/blob"
BLOB_API_VERSION = os.getenv("VERCEL_BLOB_API_VERSION_OVERRIDE") or "11"


@dataclass(frozen=True)
class _BlobAuth:
    token: str
    store_id: str
    mode: str  # "oidc" | "rw_token"


def fixed_pathname(document_id: str) -> str:
    return f"fixed/{document_id}_fixed.docx"


def fixed_filename(document_id: str) -> str:
    return f"{document_id}_fixed.docx"


def write_temp_upload(document_id: str, content: bytes) -> Path:
    """Write an uploaded DOCX into the runtime uploads directory for this request."""
    ensure_runtime_dirs()
    path = UPLOADS_DIR / f"{document_id}.docx"
    path.write_bytes(content)
    return path


def temp_fixed_path(document_id: str) -> Path:
    ensure_runtime_dirs()
    return FIXED_DIR / fixed_filename(document_id)


def save_fixed_document(document_id: str, source_path: Path) -> str:
    """
    Persist a fixed DOCX so /documents/download/{id} can retrieve it later.

    Returns a logical path string for the existing response schema.
    """
    if not source_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Fixed document was not created successfully.",
        )

    if USE_BLOB_STORAGE:
        return _save_fixed_to_blob(document_id, source_path)

    ensure_runtime_dirs()
    destination = temp_fixed_path(document_id)
    if source_path.resolve() != destination.resolve():
        destination.write_bytes(source_path.read_bytes())
    # Return a logical pathname (never an absolute host filesystem path).
    return fixed_pathname(document_id)


def load_fixed_document(document_id: str) -> tuple[bytes, str]:
    """
    Load a previously persisted fixed DOCX.

    Returns (content_bytes, download_filename).
    """
    if USE_BLOB_STORAGE:
        return _load_fixed_from_blob(document_id)

    path = temp_fixed_path(document_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fixed document not found.")
    return path.read_bytes(), fixed_filename(document_id)


def _normalize_store_id(store_id: str) -> str:
    value = store_id.strip()
    if value.startswith("store_"):
        return value[len("store_") :]
    return value


def _resolve_rw_token() -> Optional[str]:
    return os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv(
        "VERCEL_BLOB_READ_WRITE_TOKEN"
    )


def _resolve_store_id() -> Optional[str]:
    raw = os.getenv("BLOB_STORE_ID") or os.getenv("VERCEL_BLOB_STORE_ID")
    if not raw:
        return None
    return _normalize_store_id(raw)


def _resolve_oidc_token() -> str:
    """
    Resolve the short-lived Vercel OIDC token.

    Prefer the platform-provided env var, then the SDK helper which can also
    read the x-vercel-oidc-token request header when middleware registered it.
    """
    env_token = os.getenv("VERCEL_OIDC_TOKEN")
    if env_token:
        return env_token

    try:
        from vercel.oidc import get_vercel_oidc_token_sync
    except ImportError as exc:
        raise RuntimeError(
            "vercel.oidc is unavailable; install the 'vercel' package."
        ) from exc

    return get_vercel_oidc_token_sync()


def _extract_store_id_from_rw_token(token: str) -> Optional[str]:
    # RW tokens look like: vercel_blob_rw_<storeId>_<secret>
    parts = token.split("_")
    if len(parts) > 3 and parts[0] == "vercel" and parts[1] == "blob":
        return parts[3] or None
    return None


def _resolve_blob_auth() -> _BlobAuth:
    """
    Auth precedence:
    1. Explicit BLOB_READ_WRITE_TOKEN (optional fallback)
    2. On-platform OIDC (VERCEL_OIDC_TOKEN + BLOB_STORE_ID)
    """
    rw_token = _resolve_rw_token()
    if rw_token:
        store_id = _extract_store_id_from_rw_token(rw_token) or _resolve_store_id()
        if not store_id:
            raise RuntimeError(
                "BLOB_READ_WRITE_TOKEN is set but store id could not be determined. "
                "Set BLOB_STORE_ID as well."
            )
        return _BlobAuth(token=rw_token, store_id=store_id, mode="rw_token")

    store_id = _resolve_store_id()
    if not store_id:
        raise RuntimeError(
            "Private Vercel Blob requires BLOB_STORE_ID when using OIDC. "
            "Connect the Blob store to this project or set BLOB_STORE_ID."
        )

    oidc_token = _resolve_oidc_token()
    if not oidc_token:
        raise RuntimeError(
            "VERCEL_OIDC_TOKEN is missing. Enable OIDC for this Vercel project."
        )

    return _BlobAuth(token=oidc_token, store_id=store_id, mode="oidc")


def _blob_request_id(store_id: str) -> str:
    return f"{store_id}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}"


def _put_private_blob(pathname: str, content: bytes, auth: _BlobAuth) -> None:
    """Upload a private blob using the Blob HTTP API (OIDC or RW token)."""
    import httpx

    headers = {
        "authorization": f"Bearer {auth.token}",
        "x-api-version": str(BLOB_API_VERSION),
        "x-api-blob-request-id": _blob_request_id(auth.store_id),
        "x-api-blob-request-attempt": "0",
        "x-vercel-blob-access": "private",
        "x-content-type": DOCX_MEDIA_TYPE,
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.put(
            BLOB_API_URL,
            params={"pathname": pathname},
            headers=headers,
            content=content,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Blob put failed with status {response.status_code}: "
            f"{_safe_response_snippet(response.text)}"
        )


def _get_private_blob(pathname: str, auth: _BlobAuth) -> bytes:
    """Download a private blob using the authenticated store URL."""
    import httpx

    encoded_path = "/".join(quote(part, safe="") for part in pathname.split("/"))
    url = f"https://{auth.store_id}.private.blob.vercel-storage.com/{encoded_path}"
    headers = {
        "authorization": f"Bearer {auth.token}",
    }

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)

    if response.status_code == 404:
        raise FileNotFoundError(f"Blob not found at pathname '{pathname}'.")

    if response.status_code >= 400:
        raise RuntimeError(
            f"Blob get failed with status {response.status_code}: "
            f"{_safe_response_snippet(response.text)}"
        )

    return response.content


def _safe_response_snippet(text: str, limit: int = 240) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > limit:
        return cleaned[:limit] + "…"
    return cleaned


def _log_blob_failure(operation: str, exc: Exception) -> None:
    logger.exception(
        "Vercel Blob %s failed (%s): %s",
        operation,
        type(exc).__name__,
        str(exc),
    )


def _save_fixed_to_blob(document_id: str, source_path: Path) -> str:
    pathname = fixed_pathname(document_id)

    try:
        auth = _resolve_blob_auth()
        _put_private_blob(pathname, source_path.read_bytes(), auth)
    except Exception as exc:
        _log_blob_failure("put", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to store the fixed document in private Vercel Blob. "
                "Ensure the private Blob store is connected and OIDC is enabled "
                f"({type(exc).__name__})."
            ),
        ) from exc

    return pathname


def _load_fixed_from_blob(document_id: str) -> tuple[bytes, str]:
    pathname = fixed_pathname(document_id)

    try:
        auth = _resolve_blob_auth()
        content = _get_private_blob(pathname, auth)
    except FileNotFoundError as exc:
        _log_blob_failure("get", exc)
        raise HTTPException(status_code=404, detail="Fixed document not found.") from exc
    except Exception as exc:
        _log_blob_failure("get", exc)
        raise HTTPException(
            status_code=404,
            detail="Fixed document not found.",
        ) from exc

    if content is None:
        raise HTTPException(status_code=404, detail="Fixed document not found.")

    return content, fixed_filename(document_id)
