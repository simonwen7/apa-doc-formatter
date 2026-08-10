"""Upload validation and user-bound expiring download tokens (Phase 3C).

HMAC tokens are defense-in-depth only. Ownership (Bearer auth + owner-scoped
storage) is the primary authorization. A leaked token alone must not allow
another authenticated user to download a document.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time

from fastapi import HTTPException

from app.core.config import resolve_download_secret, download_token_ttl_seconds


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Keep aligned with frontend MAX_FILE_SIZE.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_DOCX_MAGIC = b"PK\x03\x04"


def validate_document_id(document_id: str) -> str:
    if not document_id or not _UUID_RE.fullmatch(document_id.strip()):
        raise HTTPException(status_code=400, detail="Invalid document id.")
    return document_id.strip()


def validate_user_id(user_id: str) -> str:
    if not user_id or not _UUID_RE.fullmatch(user_id.strip()):
        raise HTTPException(status_code=400, detail="Invalid user id.")
    return user_id.strip()


def make_download_token(
    *,
    user_id: str,
    document_id: str,
    ttl_seconds: int | None = None,
    now: int | None = None,
) -> str:
    """
    Create a short-lived HMAC token bound to user_id + document_id + expiry.

    Format: {expires_at}.{hex_hmac}
    Payload signed: download:{user_id}:{document_id}:{expires_at}
    """
    user_id = validate_user_id(user_id)
    document_id = validate_document_id(document_id)
    ttl = download_token_ttl_seconds() if ttl_seconds is None else int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")
    expires_at = int(now if now is not None else time.time()) + ttl
    secret = resolve_download_secret()
    payload = f"download:{user_id}:{document_id}:{expires_at}"
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expires_at}.{digest}"


def verify_download_token(
    *,
    user_id: str,
    document_id: str,
    token: str | None,
    now: int | None = None,
) -> None:
    """Verify user-bound expiring download token. Raises 404 on failure (anti-enum)."""
    # Use 404 for authz failures on download to avoid cross-user existence leaks
    # when combined with missing objects. Token failures still 404 consistently.
    def _deny() -> None:
        raise HTTPException(status_code=404, detail="Fixed document not found.")

    if not token or "." not in token:
        _deny()

    try:
        user_id = validate_user_id(user_id)
        document_id = validate_document_id(document_id)
    except HTTPException:
        _deny()

    expires_raw, _, digest = token.partition(".")
    try:
        expires_at = int(expires_raw)
    except ValueError:
        _deny()

    current = int(now if now is not None else time.time())
    if current > expires_at:
        _deny()

    try:
        secret = resolve_download_secret()
    except RuntimeError:
        _deny()

    payload = f"download:{user_id}:{document_id}:{expires_at}"
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not digest or not hmac.compare_digest(expected, digest):
        _deny()


def validate_docx_upload(*, filename: str | None, content: bytes) -> None:
    name = (filename or "").lower()
    if not name.endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are supported.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File exceeds the 10 MB upload limit.",
        )
    if not content.startswith(_DOCX_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid .docx package.",
        )
