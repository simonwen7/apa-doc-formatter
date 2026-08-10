"""Phase 3D: config validation + Blob list/delete provider-shape tests."""

from __future__ import annotations

import json
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
    """Mock Vercel Blob list/delete HTTP shapes used by document_store."""
    import httpx

    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    doc_keep = str(uuid4())
    doc_expire = str(uuid4())
    user_b = "22222222-2222-4222-8222-222222222222"

    list_payload = {
        "blobs": [
            {
                "pathname": f"fixed/{USER_A}/{doc_keep}.docx",
                "uploadedAt": "2026-08-09T10:00:00.000Z",
            },
            {
                "pathname": f"fixed/{user_b}/{doc_expire}.docx",
                "uploadedAt": "2026-08-01T10:00:00.000Z",
            },
            {
                "pathname": f"fixed/{user_b}/{doc_expire}.meta.json",
                "uploadedAt": "2026-08-01T10:00:00.000Z",
            },
            {
                "pathname": "uploads/should-not-touch.docx",
                "uploadedAt": "2020-01-01T00:00:00.000Z",
            },
            {
                "pathname": "fixed/bad/not-uuid.docx",
                "uploadedAt": "2020-01-01T00:00:00.000Z",
            },
        ],
        "hasMore": False,
        "cursor": None,
    }

    deleted: list[str] = []

    class FakeResponse:
        def __init__(self, status_code=200, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text or json.dumps(self._payload)

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None, params=None):
            if params and params.get("prefix") == "fixed/":
                return FakeResponse(200, list_payload)
            # meta get
            return FakeResponse(
                200,
                text=json.dumps({"created_at": 1.0, "document_id": doc_expire}),
            )

        def post(self, url, headers=None, json=None):
            if url.endswith("/delete"):
                for item in (json or {}).get("urls") or []:
                    deleted.append(item)
                return FakeResponse(200, {"ok": True})
            return FakeResponse(400, text="bad")

        def delete(self, url, headers=None, params=None):
            return FakeResponse(200, {"ok": True})

        def put(self, *args, **kwargs):
            return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(
        document_store,
        "_resolve_blob_auth",
        lambda: document_store._BlobAuth(
            token="token", store_id="store123", mode="rw_token"
        ),
    )

    # Intercept meta content reads used during enrichment.
    def fake_get(pathname, auth):
        if pathname.endswith(".meta.json"):
            return json.dumps(
                {"created_at": 1.0, "document_id": doc_expire}
            ).encode("utf-8")
        raise FileNotFoundError(pathname)

    monkeypatch.setattr(document_store, "_get_private_blob", fake_get)

    objects = document_store._list_fixed_from_blob()
    pathnames = {o.pathname for o in objects}
    assert any(doc_keep in p for p in pathnames)
    assert any(doc_expire in p for p in pathnames)
    assert not any(p.startswith("uploads/") for p in pathnames)

    # Age one object and run cleanup using returned objects.
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
    # retention_cleanup imports delete_fixed_document at module level — patch there too
    import app.services.retention_cleanup as cleanup_mod

    monkeypatch.setattr(cleanup_mod, "delete_fixed_document", fake_delete)

    report = cleanup_expired_fixed_documents(
        retention_hours=24, now=now, objects=aged
    )
    assert report.expired >= 1
    assert doc_expire in deleted_ids
    assert doc_keep not in deleted_ids


def test_blob_list_provider_error_is_safe(monkeypatch):
    import httpx

    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)

    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            class R:
                status_code = 500
                text = "provider failure"

                def json(self):
                    return {}

            return R()

    monkeypatch.setattr(httpx, "Client", BoomClient)
    monkeypatch.setattr(
        document_store,
        "_resolve_blob_auth",
        lambda: document_store._BlobAuth(
            token="token", store_id="store123", mode="rw_token"
        ),
    )

    with pytest.raises(RuntimeError):
        document_store._list_fixed_from_blob()

    report = cleanup_expired_fixed_documents()
    # list failure should not crash batch with uncaught exception when using
    # cleanup's try/except — monkeypatch list to raise
    import app.services.retention_cleanup as cleanup_mod

    def boom_list():
        raise RuntimeError("provider")

    monkeypatch.setattr(cleanup_mod, "list_fixed_objects", boom_list)
    report = cleanup_expired_fixed_documents()
    assert len(report.errors) >= 1
