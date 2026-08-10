"""Phase 3D: config validation + Blob list/delete provider-shape tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth_deps import AuthenticatedUser, reset_token_verifier, set_token_verifier
from app.core import config as app_config
from app.core.config import parse_cors_origins, parse_positive_int
from app.main import app
from app.services import document_store
from app.services.document_store import StoredFixedObject, _parse_fixed_pathname
from app.services.retention_cleanup import cleanup_expired_fixed_documents

USER_A = "11111111-1111-4111-8111-111111111111"
TOKEN_A = "access-token-user-a"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "IS_PRODUCTION", False)
    monkeypatch.setattr(app_config, "CRON_SECRET", "cron-secret-value-32chars-aaaa")
    monkeypatch.setattr(app_config, "CLEANUP_JOB_SECRET", "cleanup-secret-for-tests")
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(document_store, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(document_store, "UPLOADS_DIR", tmp_path / "uploads")

    def verifier(token: str) -> AuthenticatedUser:
        from fastapi import HTTPException

        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        raise HTTPException(status_code=401, detail="Authentication required.")

    set_token_verifier(verifier)
    yield
    reset_token_verifier()


def test_parse_positive_int_rejects_invalid():
    assert parse_positive_int("X", None, default=24) == 24
    with pytest.raises(ValueError):
        parse_positive_int("DOCUMENT_RETENTION_HOURS", "0", default=24)
    with pytest.raises(ValueError):
        parse_positive_int("DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS", "-1", default=1)
    with pytest.raises(ValueError):
        parse_positive_int("DOCUMENT_RETENTION_HOURS", "abc", default=24)


def test_parse_cors_rejects_wildcard_and_paths():
    origins = parse_cors_origins("https://app.example.com")
    assert "https://app.example.com" in origins
    assert "http://localhost:5173" in origins

    with pytest.raises(ValueError):
        parse_cors_origins("*")
    with pytest.raises(ValueError):
        parse_cors_origins("https://app.example.com/path")
    with pytest.raises(ValueError):
        parse_cors_origins("not-a-url")


def test_production_download_secret_failures(monkeypatch):
    monkeypatch.setattr(app_config, "IS_PRODUCTION", True)
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", None)
    with pytest.raises(RuntimeError):
        app_config.resolve_download_secret()

    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        app_config.resolve_download_secret()


def test_cleanup_accepts_cron_bearer_and_manual_header():
    client = TestClient(app)

    denied = client.get("/internal/cleanup-fixed-documents")
    assert denied.status_code == 401

    cron_ok = client.get(
        "/internal/cleanup-fixed-documents",
        headers={"Authorization": "Bearer cron-secret-value-32chars-aaaa"},
    )
    assert cron_ok.status_code == 200
    assert cron_ok.json()["ok"] is True

    manual_ok = client.post(
        "/internal/cleanup-fixed-documents",
        headers={"X-Cleanup-Secret": "cleanup-secret-for-tests"},
    )
    assert manual_ok.status_code == 200


def test_parse_fixed_pathname_rejects_unrelated_and_malformed():
    doc = str(uuid4())
    assert _parse_fixed_pathname(f"fixed/{USER_A}/{doc}.docx") == (USER_A, doc)
    assert _parse_fixed_pathname(f"fixed/{USER_A}/{doc}.meta.json") == (USER_A, doc)
    assert _parse_fixed_pathname("other/namespace/file.docx") is None
    assert _parse_fixed_pathname("fixed/not-a-uuid/file.docx") is None
    assert _parse_fixed_pathname(f"fixed/{USER_A}/nope.txt") is None


def test_blob_list_provider_shape_and_delete(monkeypatch, tmp_path):
    """Mock official BlobClient list/delete used by document_store cleanup."""
    from datetime import datetime, timezone

    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_storeTEST_fake")
    doc_keep = str(uuid4())
    doc_expire = str(uuid4())
    user_b = "22222222-2222-4222-8222-222222222222"

    @dataclass
    class Item:
        pathname: str
        uploaded_at: datetime
        url: str = ""
        download_url: str = ""
        size: int = 1

    @dataclass
    class Page:
        blobs: list
        cursor: str | None = None
        has_more: bool = False
        folders: list | None = None

    class FakeClient:
        def __init__(self):
            self.deletes: list[str] = []

        def list_objects(self, *, prefix=None, cursor=None, limit=None, **kwargs):
            blobs = [
                Item(
                    pathname=f"fixed/{USER_A}/{doc_keep}.docx",
                    uploaded_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
                ),
                Item(
                    pathname=f"fixed/{user_b}/{doc_expire}.docx",
                    uploaded_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                ),
                Item(
                    pathname=f"fixed/{user_b}/{doc_expire}.meta.json",
                    uploaded_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                ),
                Item(
                    pathname="uploads/should-not-touch.docx",
                    uploaded_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                ),
                Item(
                    pathname="fixed/bad/not-uuid.docx",
                    uploaded_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                ),
            ]
            return Page(blobs=blobs)

        def get(self, pathname, *, access="public", **kwargs):
            class R:
                content = json.dumps(
                    {"created_at": 1.0, "document_id": doc_expire}
                ).encode("utf-8")

            return R()

        def delete(self, pathname, **kwargs):
            self.deletes.append(pathname)

        def put(self, *args, **kwargs):
            return None

    fake = FakeClient()
    monkeypatch.setattr(document_store, "_blob_client", lambda: fake)

    objects = document_store._list_fixed_from_blob()
    pathnames = {o.pathname for o in objects}
    assert any(doc_keep in p for p in pathnames)
    assert any(doc_expire in p for p in pathnames)
    assert not any(p.startswith("uploads/") for p in pathnames)

    import time

    now = time.time()
    aged = []
    for obj in objects:
        if doc_expire in obj.pathname:
            aged.append(
                StoredFixedObject(
                    pathname=obj.pathname,
                    user_id=obj.user_id,
                    document_id=obj.document_id,
                    created_at=now - 48 * 3600,
                )
            )
        else:
            aged.append(
                StoredFixedObject(
                    pathname=obj.pathname,
                    user_id=obj.user_id,
                    document_id=obj.document_id,
                    created_at=now,
                )
            )

    deleted_ids: list[str] = []

    def fake_delete(user_id, document_id):
        deleted_ids.append(document_id)
        return True

    monkeypatch.setattr(document_store, "delete_fixed_document", fake_delete)
    import app.services.retention_cleanup as cleanup_mod

    monkeypatch.setattr(cleanup_mod, "delete_fixed_document", fake_delete)

    report = cleanup_expired_fixed_documents(
        retention_hours=24, now=now, objects=aged
    )
    assert report.expired >= 1
    assert doc_expire in deleted_ids
    assert doc_keep not in deleted_ids


def test_blob_list_provider_error_is_safe(monkeypatch):
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_storeTEST_fake")

    class BoomClient:
        def list_objects(self, **kwargs):
            raise RuntimeError("provider")

    monkeypatch.setattr(document_store, "_blob_client", lambda: BoomClient())

    with pytest.raises(document_store.BlobStorageError):
        document_store._list_fixed_from_blob()

    import app.services.retention_cleanup as cleanup_mod

    def boom_list():
        raise RuntimeError("provider")

    monkeypatch.setattr(cleanup_mod, "list_fixed_objects", boom_list)
    report = cleanup_expired_fixed_documents()
    assert len(report.errors) >= 1
