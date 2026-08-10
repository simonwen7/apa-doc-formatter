"""Persistent owner-scoped document storage for analyze/fix/download.

Storage key model (Phase 3C):
    fixed/{user_id}/{document_id}.docx

Ownership is inherent in the pathname. Download for user A never scans user B's
folder. Local and Blob modes share the same logical pathname.
"""

from __future__ import annotations

import json
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
    FIXED_BLOB_NAMESPACE,
    FIXED_DIR,
    UPLOADS_DIR,
    USE_BLOB_STORAGE,
    ensure_runtime_dirs,
)
from app.services.download_auth import validate_document_id, validate_user_id

logger = logging.getLogger(__name__)

BLOB_API_URL = os.getenv("VERCEL_BLOB_API_URL") or "https://vercel.com/api/blob"
BLOB_API_VERSION = os.getenv("VERCEL_BLOB_API_VERSION_OVERRIDE") or "11"


@dataclass(frozen=True)
class _BlobAuth:
    token: str
    store_id: str
    mode: str  # "oidc" | "rw_token"


@dataclass(frozen=True)
class StoredFixedObject:
    pathname: str
    user_id: str
    document_id: str
    created_at: float


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


def save_fixed_document(
    user_id: str,
    document_id: str,
    source_path: Path,
    *,
    oidc_token: str | None = None,
) -> str:
    """
    Persist a fixed DOCX under the verified owner's namespace.

    Returns the logical pathname (never a host filesystem path or Blob URL).
    `oidc_token` is Vercel infrastructure auth from `x-vercel-oidc-token`
    (never the Supabase user Bearer).
    """
    if not source_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Fixed document was not created successfully.",
        )

    pathname = fixed_pathname(user_id, document_id)
    created_at = time.time()

    if USE_BLOB_STORAGE:
        return _save_fixed_to_blob(
            user_id,
            document_id,
            source_path,
            created_at,
            oidc_token=oidc_token,
        )

    FIXED_DIR.mkdir(parents=True, exist_ok=True)
    destination = temp_fixed_path(user_id, document_id)
    if source_path.resolve() != destination.resolve():
        destination.write_bytes(source_path.read_bytes())
    _write_local_meta(user_id, document_id, created_at)
    return pathname


def load_fixed_document(
    user_id: str,
    document_id: str,
    *,
    oidc_token: str | None = None,
) -> tuple[bytes, str]:
    """
    Load a previously persisted fixed DOCX for the verified owner only.

    Missing or cross-user lookups return the same 404.
    """
    if USE_BLOB_STORAGE:
        return _load_fixed_from_blob(user_id, document_id, oidc_token=oidc_token)

    path = temp_fixed_path(user_id, document_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fixed document not found.")
    return path.read_bytes(), fixed_filename(document_id)


def delete_fixed_document(
    user_id: str,
    document_id: str,
    *,
    oidc_token: str | None = None,
) -> bool:
    """Delete one owner-scoped fixed document. Returns True if deleted/missing OK."""
    pathname = fixed_pathname(user_id, document_id)
    meta_pathname = fixed_meta_pathname(user_id, document_id)

    if USE_BLOB_STORAGE:
        try:
            auth = _resolve_blob_auth(oidc_token=oidc_token)
            _delete_private_blob(pathname, auth)
            _delete_private_blob(meta_pathname, auth)
            return True
        except Exception as exc:
            _log_blob_failure("delete", exc)
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


def list_fixed_objects(*, oidc_token: str | None = None) -> list[StoredFixedObject]:
    """List fixed documents under the approved namespace only."""
    if USE_BLOB_STORAGE:
        return _list_fixed_from_blob(oidc_token=oidc_token)
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


def _resolve_oidc_token(*, oidc_token: str | None = None) -> str:
    """
    Resolve Vercel infrastructure OIDC for Blob.

    Preference (official Function runtime model):
    1. Explicit token from the current request's `x-vercel-oidc-token`
    2. vercel.oidc helper (ContextVar headers, then env for builds/CLI)
    3. VERCEL_OIDC_TOKEN env (builds / vercel env pull) as last resort

    Never read the Supabase `Authorization` Bearer here.
    """
    explicit = (oidc_token or "").strip()
    if explicit:
        return explicit

    try:
        from vercel.oidc import get_vercel_oidc_token_sync

        return get_vercel_oidc_token_sync()
    except Exception:
        env_token = (os.getenv("VERCEL_OIDC_TOKEN") or "").strip()
        if env_token:
            return env_token
        raise RuntimeError(
            "Vercel OIDC token unavailable for Blob. "
            "Ensure the Function request includes x-vercel-oidc-token "
            "and OIDC is enabled for the project."
        ) from None


def _extract_store_id_from_rw_token(token: str) -> Optional[str]:
    parts = token.split("_")
    if len(parts) > 3 and parts[0] == "vercel" and parts[1] == "blob":
        return parts[3] or None
    return None


def _resolve_blob_auth(*, oidc_token: str | None = None) -> _BlobAuth:
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

    resolved = _resolve_oidc_token(oidc_token=oidc_token)
    return _BlobAuth(token=resolved, store_id=store_id, mode="oidc")


def _blob_request_id(store_id: str) -> str:
    return f"{store_id}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}"


def _put_private_blob(pathname: str, content: bytes, auth: _BlobAuth) -> None:
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
    import httpx

    encoded_path = "/".join(quote(part, safe="") for part in pathname.split("/"))
    url = f"https://{auth.store_id}.private.blob.vercel-storage.com/{encoded_path}"
    headers = {"authorization": f"Bearer {auth.token}"}

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


def _delete_private_blob(pathname: str, auth: _BlobAuth) -> None:
    """Delete by pathname. Missing objects are treated as success."""
    import httpx

    # Official Blob del accepts URL or pathname. Prefer private URL form.
    encoded_path = "/".join(quote(part, safe="") for part in pathname.split("/"))
    url = f"https://{auth.store_id}.private.blob.vercel-storage.com/{encoded_path}"
    headers = {
        "authorization": f"Bearer {auth.token}",
        "x-api-version": str(BLOB_API_VERSION),
        "x-api-blob-request-id": _blob_request_id(auth.store_id),
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{BLOB_API_URL}/delete",
            headers=headers,
            json={"urls": [url]},
        )
        # Some API versions use DELETE with body; tolerate 404 / already gone.
        if response.status_code >= 400 and response.status_code != 404:
            # Try alternate delete shape with pathname.
            response = client.delete(
                BLOB_API_URL,
                headers=headers,
                params={"pathname": pathname},
            )
            if response.status_code >= 400 and response.status_code != 404:
                raise RuntimeError(
                    f"Blob delete failed with status {response.status_code}: "
                    f"{_safe_response_snippet(response.text)}"
                )


def _list_fixed_from_blob(*, oidc_token: str | None = None) -> list[StoredFixedObject]:
    import httpx

    auth = _resolve_blob_auth(oidc_token=oidc_token)
    headers = {
        "authorization": f"Bearer {auth.token}",
        "x-api-version": str(BLOB_API_VERSION),
        "x-api-blob-request-id": _blob_request_id(auth.store_id),
    }
    results: list[StoredFixedObject] = []
    cursor = None

    with httpx.Client(timeout=60.0) as client:
        while True:
            params: dict[str, str] = {"prefix": FIXED_BLOB_NAMESPACE, "limit": "1000"}
            if cursor:
                params["cursor"] = cursor
            response = client.get(BLOB_API_URL, headers=headers, params=params)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Blob list failed with status {response.status_code}: "
                    f"{_safe_response_snippet(response.text)}"
                )
            payload = response.json()
            blobs = payload.get("blobs") or payload.get("data") or []
            for item in blobs:
                pathname = item.get("pathname") or item.get("path") or ""
                parsed = _parse_fixed_pathname(pathname)
                if not parsed:
                    continue
                user_id, document_id = parsed
                uploaded = item.get("uploadedAt") or item.get("uploaded_at")
                created_at = time.time()
                if uploaded:
                    try:
                        # ISO8601 or epoch
                        if isinstance(uploaded, (int, float)):
                            created_at = float(uploaded)
                        else:
                            from datetime import datetime

                            created_at = datetime.fromisoformat(
                                str(uploaded).replace("Z", "+00:00")
                            ).timestamp()
                    except Exception:
                        created_at = time.time()
                results.append(
                    StoredFixedObject(
                        pathname=pathname,
                        user_id=user_id,
                        document_id=document_id,
                        created_at=created_at,
                    )
                )
            cursor = payload.get("cursor")
            if not payload.get("hasMore") and not payload.get("has_more"):
                break
            if not cursor:
                break

    # Prefer meta created_at when present.
    meta_by_doc = {
        (o.user_id, o.document_id): o
        for o in results
        if o.pathname.endswith(".meta.json")
    }
    # Filter to .docx only for cleanup candidates.
    docs = [o for o in results if o.pathname.endswith(".docx")]
    enriched: list[StoredFixedObject] = []
    for obj in docs:
        meta = meta_by_doc.get((obj.user_id, obj.document_id))
        if meta:
            # Load meta content when possible for precise age.
            try:
                raw = _get_private_blob(meta.pathname, auth)
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


def _safe_response_snippet(text: str, limit: int = 240) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > limit:
        return cleaned[:limit] + "…"
    return cleaned


def _log_blob_failure(operation: str, exc: Exception) -> None:
    # Never log token values or exception messages (may echo provider bodies).
    logger.error(
        "Vercel Blob %s failed (%s)",
        operation,
        type(exc).__name__,
    )


def _save_fixed_to_blob(
    user_id: str,
    document_id: str,
    source_path: Path,
    created_at: float,
    *,
    oidc_token: str | None = None,
) -> str:
    pathname = fixed_pathname(user_id, document_id)
    meta_pathname = fixed_meta_pathname(user_id, document_id)

    try:
        auth = _resolve_blob_auth(oidc_token=oidc_token)
        _put_private_blob(pathname, source_path.read_bytes(), auth)
        meta_bytes = json.dumps(
            {"created_at": created_at, "document_id": document_id}
        ).encode("utf-8")
        import httpx

        headers = {
            "authorization": f"Bearer {auth.token}",
            "x-api-version": str(BLOB_API_VERSION),
            "x-api-blob-request-id": _blob_request_id(auth.store_id),
            "x-api-blob-request-attempt": "0",
            "x-vercel-blob-access": "private",
            "x-content-type": "application/json",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.put(
                BLOB_API_URL,
                params={"pathname": meta_pathname},
                headers=headers,
                content=meta_bytes,
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Blob meta put failed with status {response.status_code}: "
                f"{_safe_response_snippet(response.text)}"
            )
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


def _load_fixed_from_blob(
    user_id: str,
    document_id: str,
    *,
    oidc_token: str | None = None,
) -> tuple[bytes, str]:
    pathname = fixed_pathname(user_id, document_id)

    try:
        auth = _resolve_blob_auth(oidc_token=oidc_token)
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
