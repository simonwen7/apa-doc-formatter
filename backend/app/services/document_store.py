"""Persistent owner-scoped document storage for analyze/fix/download.

Storage key model (Phase 3C):
    fixed/{user_id}/{document_id}.docx

Ownership is inherent in the pathname. Download for user A never scans user B's
folder. Local and Blob modes share the same logical pathname.

On Vercel, persistence uses the official Python `vercel.blob.BlobClient` with
`BLOB_READ_WRITE_TOKEN` (or `VERCEL_BLOB_READ_WRITE_TOKEN`). Private access is
required for every put/get. Blob URLs are never returned to the client.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from app.core.config import (
    DOCX_MEDIA_TYPE,
    FIXED_BLOB_NAMESPACE,
    FIXED_DIR,
    UPLOADS_DIR,
    USE_BLOB_STORAGE,
    ensure_runtime_dirs,
)
from app.services.download_auth import validate_document_id, validate_user_id

logger = logging.getLogger(__name__)

# Internal diagnostic categories (never include secrets).
BLOB_AUTH_FAILED = "BLOB_AUTH_FAILED"
BLOB_WRITE_FAILED = "BLOB_WRITE_FAILED"
BLOB_READ_FAILED = "BLOB_READ_FAILED"
BLOB_LIST_FAILED = "BLOB_LIST_FAILED"
BLOB_DELETE_FAILED = "BLOB_DELETE_FAILED"


@dataclass(frozen=True)
class StoredFixedObject:
    pathname: str
    user_id: str
    document_id: str
    created_at: float


class BlobStorageError(RuntimeError):
    """Provider failure with a safe internal category (no credentials)."""

    def __init__(self, category: str, *, cause: Exception | None = None):
        self.category = category
        super().__init__(category)
        self.__cause__ = cause


def fixed_pathname(user_id: str, document_id: str) -> str:
    user_id = validate_user_id(user_id)
    document_id = validate_document_id(document_id)
    return f"fixed/{user_id}/{document_id}.docx"


def fixed_meta_pathname(user_id: str, document_id: str) -> str:
    user_id = validate_user_id(user_id)
    document_id = validate_document_id(document_id)
    return f"fixed/{user_id}/{document_id}.meta.json"


def fixed_filename(document_id: str) -> str:
    document_id = validate_document_id(document_id)
    return f"{document_id}.docx"


def write_temp_upload(document_id: str, content: bytes) -> Path:
    """Write an uploaded DOCX into the runtime uploads directory for this request."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOADS_DIR / f"{document_id}.docx"
    path.write_bytes(content)
    return path


def temp_fixed_path(user_id: str, document_id: str) -> Path:
    user_id = validate_user_id(user_id)
    document_id = validate_document_id(document_id)
    owner_dir = FIXED_DIR / user_id
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir / fixed_filename(document_id)


def _local_meta_path(user_id: str, document_id: str) -> Path:
    return FIXED_DIR / user_id / f"{document_id}.meta.json"


def _write_local_meta(user_id: str, document_id: str, created_at: float) -> None:
    meta = _local_meta_path(user_id, document_id)
    meta.write_text(
        json.dumps({"created_at": created_at, "document_id": document_id}),
        encoding="utf-8",
    )


def save_fixed_document(user_id: str, document_id: str, source_path: Path) -> str:
    """
    Persist a fixed DOCX under the verified owner's namespace.

    Returns the logical pathname (never a host filesystem path or Blob URL).
    """
    if not source_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Fixed document was not created successfully.",
        )

    pathname = fixed_pathname(user_id, document_id)
    created_at = time.time()

    if USE_BLOB_STORAGE:
        return _save_fixed_to_blob(user_id, document_id, source_path, created_at)

    FIXED_DIR.mkdir(parents=True, exist_ok=True)
    destination = temp_fixed_path(user_id, document_id)
    if source_path.resolve() != destination.resolve():
        destination.write_bytes(source_path.read_bytes())
    _write_local_meta(user_id, document_id, created_at)
    return pathname


def load_fixed_document(user_id: str, document_id: str) -> tuple[bytes, str]:
    """
    Load a previously persisted fixed DOCX for the verified owner only.

    Missing or cross-user lookups return the same 404.
    """
    if USE_BLOB_STORAGE:
        return _load_fixed_from_blob(user_id, document_id)

    path = temp_fixed_path(user_id, document_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fixed document not found.")
    return path.read_bytes(), fixed_filename(document_id)


def delete_fixed_document(user_id: str, document_id: str) -> bool:
    """Delete one owner-scoped fixed document. Returns True if deleted/missing OK."""
    pathname = fixed_pathname(user_id, document_id)
    meta_pathname = fixed_meta_pathname(user_id, document_id)

    if USE_BLOB_STORAGE:
        try:
            client = _blob_client()
            _sdk_delete(client, pathname)
            _sdk_delete(client, meta_pathname)
            return True
        except Exception as exc:
            _log_blob_failure("delete", BLOB_DELETE_FAILED, exc)
            return False

    path = temp_fixed_path(user_id, document_id)
    meta = _local_meta_path(user_id, document_id)
    deleted = False
    if path.exists():
        path.unlink()
        deleted = True
    if meta.exists():
        meta.unlink()
        deleted = True
    return deleted


def list_fixed_objects() -> list[StoredFixedObject]:
    """List fixed documents under the approved namespace only."""
    if USE_BLOB_STORAGE:
        return _list_fixed_from_blob()
    return _list_fixed_from_local()


def _list_fixed_from_local() -> list[StoredFixedObject]:
    ensure_runtime_dirs()
    results: list[StoredFixedObject] = []
    if not FIXED_DIR.exists():
        return results

    for user_dir in FIXED_DIR.iterdir():
        if not user_dir.is_dir():
            continue
        try:
            user_id = validate_user_id(user_dir.name)
        except HTTPException:
            continue
        for path in user_dir.glob("*.docx"):
            document_id = path.stem
            try:
                validate_document_id(document_id)
            except HTTPException:
                continue
            created_at = path.stat().st_mtime
            meta = _local_meta_path(user_id, document_id)
            if meta.exists():
                try:
                    payload = json.loads(meta.read_text(encoding="utf-8"))
                    created_at = float(payload.get("created_at", created_at))
                except Exception:
                    pass
            results.append(
                StoredFixedObject(
                    pathname=fixed_pathname(user_id, document_id),
                    user_id=user_id,
                    document_id=document_id,
                    created_at=created_at,
                )
            )
    return results


def _resolve_rw_token() -> Optional[str]:
    """Server-only Blob credential. Never read Supabase Authorization."""
    token = (
        os.getenv("BLOB_READ_WRITE_TOKEN")
        or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN")
        or ""
    ).strip()
    return token or None


def require_blob_rw_token() -> str:
    """Fail closed when Blob storage is required but the RW token is missing."""
    token = _resolve_rw_token()
    if not token:
        raise BlobStorageError(BLOB_AUTH_FAILED)
    return token


def _blob_client() -> Any:
    """
    Construct the official BlobClient.

    Token is resolved by the SDK from BLOB_READ_WRITE_TOKEN /
    VERCEL_BLOB_READ_WRITE_TOKEN when not passed explicitly. We still verify
    presence first so missing production config fails with BLOB_AUTH_FAILED.
    """
    require_blob_rw_token()
    try:
        from vercel.blob import BlobClient
    except ImportError as exc:
        raise BlobStorageError(BLOB_AUTH_FAILED, cause=exc) from exc

    return BlobClient()


def _classify_blob_exception(exc: Exception, *, default: str) -> str:
    name = type(exc).__name__
    message = str(exc).lower()
    if name in {"BlobNoTokenProvidedError", "BlobAccessError"} or "token" in message:
        return BLOB_AUTH_FAILED
    if name in {"BlobStoreNotFoundError"}:
        return BLOB_AUTH_FAILED
    if name in {"BlobNotFoundError"}:
        return BLOB_READ_FAILED
    return default


def _log_blob_failure(operation: str, category: str, exc: Exception) -> None:
    # Never log token values or exception messages (may echo provider bodies).
    logger.error(
        "Vercel Blob %s failed category=%s type=%s",
        operation,
        category,
        type(exc).__name__,
    )


def _sdk_put(
    client: Any,
    pathname: str,
    body: bytes,
    *,
    content_type: str,
) -> None:
    client.put(
        pathname,
        body,
        access="private",
        content_type=content_type,
        add_random_suffix=False,
        overwrite=True,
    )


def _sdk_get_bytes(client: Any, pathname: str) -> bytes:
    from vercel.blob.errors import BlobNotFoundError

    try:
        result = client.get(pathname, access="private")
    except BlobNotFoundError as exc:
        raise FileNotFoundError(pathname) from exc
    content = getattr(result, "content", None)
    if content is None:
        raise FileNotFoundError(pathname)
    return bytes(content)


def _sdk_delete(client: Any, pathname: str) -> None:
    from vercel.blob.errors import BlobNotFoundError

    try:
        client.delete(pathname)
    except BlobNotFoundError:
        return


def _uploaded_at_to_epoch(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return fallback


def _list_fixed_from_blob() -> list[StoredFixedObject]:
    try:
        client = _blob_client()
    except BlobStorageError:
        raise
    except Exception as exc:
        category = _classify_blob_exception(exc, default=BLOB_LIST_FAILED)
        _log_blob_failure("list", category, exc)
        raise BlobStorageError(category, cause=exc) from exc

    results: list[StoredFixedObject] = []
    cursor: str | None = None

    try:
        while True:
            page = client.list_objects(prefix=FIXED_BLOB_NAMESPACE, cursor=cursor, limit=1000)
            blobs = getattr(page, "blobs", None) or []
            for item in blobs:
                pathname = getattr(item, "pathname", "") or ""
                parsed = _parse_fixed_pathname(pathname)
                if not parsed:
                    continue
                user_id, document_id = parsed
                created_at = _uploaded_at_to_epoch(
                    getattr(item, "uploaded_at", None),
                    time.time(),
                )
                results.append(
                    StoredFixedObject(
                        pathname=pathname,
                        user_id=user_id,
                        document_id=document_id,
                        created_at=created_at,
                    )
                )
            has_more = bool(getattr(page, "has_more", False))
            cursor = getattr(page, "cursor", None)
            if not has_more or not cursor:
                break
    except BlobStorageError:
        raise
    except Exception as exc:
        category = _classify_blob_exception(exc, default=BLOB_LIST_FAILED)
        _log_blob_failure("list", category, exc)
        raise BlobStorageError(category, cause=exc) from exc

    meta_by_doc = {
        (o.user_id, o.document_id): o
        for o in results
        if o.pathname.endswith(".meta.json")
    }
    docs = [o for o in results if o.pathname.endswith(".docx")]
    enriched: list[StoredFixedObject] = []
    for obj in docs:
        meta = meta_by_doc.get((obj.user_id, obj.document_id))
        if meta:
            try:
                raw = _sdk_get_bytes(client, meta.pathname)
                payload = json.loads(raw.decode("utf-8"))
                created_at = float(payload.get("created_at", obj.created_at))
                enriched.append(
                    StoredFixedObject(
                        pathname=obj.pathname,
                        user_id=obj.user_id,
                        document_id=obj.document_id,
                        created_at=created_at,
                    )
                )
                continue
            except Exception:
                pass
        enriched.append(obj)
    return enriched


def _parse_fixed_pathname(pathname: str) -> tuple[str, str] | None:
    """Accept only fixed/{uuid}/{uuid}.docx (or .meta.json)."""
    if not pathname or not pathname.startswith(FIXED_BLOB_NAMESPACE):
        return None
    parts = pathname.split("/")
    if len(parts) != 3:
        return None
    _, user_id, name = parts
    if not (name.endswith(".docx") or name.endswith(".meta.json")):
        return None
    document_id = name.split(".", 1)[0]
    try:
        validate_user_id(user_id)
        validate_document_id(document_id)
    except HTTPException:
        return None
    return user_id, document_id


def _save_fixed_to_blob(
    user_id: str,
    document_id: str,
    source_path: Path,
    created_at: float,
) -> str:
    pathname = fixed_pathname(user_id, document_id)
    meta_pathname = fixed_meta_pathname(user_id, document_id)

    try:
        client = _blob_client()
        _sdk_put(
            client,
            pathname,
            source_path.read_bytes(),
            content_type=DOCX_MEDIA_TYPE,
        )
        meta_bytes = json.dumps(
            {"created_at": created_at, "document_id": document_id}
        ).encode("utf-8")
        _sdk_put(
            client,
            meta_pathname,
            meta_bytes,
            content_type="application/json",
        )
    except BlobStorageError as exc:
        _log_blob_failure("put", exc.category, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to store the fixed document in private Vercel Blob. "
                "Ensure BLOB_READ_WRITE_TOKEN is configured for this deployment."
            ),
        ) from None
    except Exception as exc:
        category = _classify_blob_exception(exc, default=BLOB_WRITE_FAILED)
        _log_blob_failure("put", category, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to store the fixed document in private Vercel Blob. "
                "Ensure BLOB_READ_WRITE_TOKEN is configured for this deployment."
            ),
        ) from None

    return pathname


def _load_fixed_from_blob(user_id: str, document_id: str) -> tuple[bytes, str]:
    pathname = fixed_pathname(user_id, document_id)

    try:
        client = _blob_client()
        content = _sdk_get_bytes(client, pathname)
    except FileNotFoundError as exc:
        _log_blob_failure("get", BLOB_READ_FAILED, exc)
        raise HTTPException(status_code=404, detail="Fixed document not found.") from None
    except BlobStorageError as exc:
        _log_blob_failure("get", exc.category, exc)
        raise HTTPException(status_code=404, detail="Fixed document not found.") from None
    except Exception as exc:
        category = _classify_blob_exception(exc, default=BLOB_READ_FAILED)
        _log_blob_failure("get", category, exc)
        raise HTTPException(status_code=404, detail="Fixed document not found.") from None

    return content, fixed_filename(document_id)
