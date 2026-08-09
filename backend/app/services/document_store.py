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
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.core.config import (
    DOCX_MEDIA_TYPE,
    FIXED_DIR,
    UPLOADS_DIR,
    USE_BLOB_STORAGE,
    ensure_runtime_dirs,
)


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
    return str(destination)


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


def _blob_client():
    try:
        from vercel.blob import BlobClient
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vercel Blob SDK is not installed. "
                "Add the 'vercel' package to backend requirements."
            ),
        ) from exc

    return BlobClient()


def _save_fixed_to_blob(document_id: str, source_path: Path) -> str:
    pathname = fixed_pathname(document_id)
    client = _blob_client()

    try:
        client.put(
            pathname,
            source_path.read_bytes(),
            access="private",
            content_type=DOCX_MEDIA_TYPE,
            add_random_suffix=False,
            overwrite=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to store the fixed document in private Vercel Blob. "
                "Create a private Blob store and set BLOB_READ_WRITE_TOKEN "
                f"(or enable Vercel OIDC for Blob). Details: {exc}"
            ),
        ) from exc

    return pathname


def _load_fixed_from_blob(document_id: str) -> tuple[bytes, str]:
    pathname = fixed_pathname(document_id)
    client = _blob_client()

    try:
        result = client.get(pathname, access="private", use_cache=False)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Fixed document not found. Details: {exc}",
        ) from exc

    content: Optional[bytes] = getattr(result, "content", None)
    if content is None:
        raise HTTPException(status_code=404, detail="Fixed document not found.")

    return content, fixed_filename(document_id)
