"""Opaque download tokens for fixed documents (Phase 3B).

Knowing a document UUID alone must not authorize download.
Tokens are HMAC-SHA256(document_id) under DOCUMENT_DOWNLOAD_SECRET
(or BLOB_READ_WRITE_TOKEN / local-dev fallback).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

from fastapi import HTTPException

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


def _download_secret() -> bytes:
    secret = (
        os.getenv("DOCUMENT_DOWNLOAD_SECRET")
        or os.getenv("BLOB_READ_WRITE_TOKEN")
        or "forma-apa-local-dev-download-secret"
    )
    return secret.encode("utf-8")


def make_download_token(document_id: str) -> str:
    validate_document_id(document_id)
    return hmac.new(
        _download_secret(),
        f"download:{document_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_download_token(document_id: str, token: str | None) -> None:
    expected = make_download_token(document_id)
    if not token or not hmac.compare_digest(expected, token):
        raise HTTPException(
            status_code=403,
            detail="Download authorization failed.",
        )


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
