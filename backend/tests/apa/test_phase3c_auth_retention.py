"""Auth/ownership/retention tests for Phase 3C (no live Supabase)."""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth_deps import AuthenticatedUser, reset_token_verifier, set_token_verifier
from app.core import config as app_config
from app.main import app
from app.services import document_store
from app.services.download_auth import make_download_token, verify_download_token
from app.services.retention_cleanup import cleanup_expired_fixed_documents
from tests.apa.golden_corpus.builders import build_b_misformatted

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
TOKEN_A = "access-token-user-a"
TOKEN_B = "access-token-user-b"


@pytest.fixture(autouse=True)
def _auth_and_storage(tmp_path, monkeypatch):
    """Isolate fixed storage and inject synthetic verified users."""
    monkeypatch.setattr(app_config, "IS_PRODUCTION", False)
    monkeypatch.setattr(app_config, "IS_VERCEL", False)
    monkeypatch.setattr(app_config, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(app_config, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(app_config, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(document_store, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(document_store, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setenv("DOCUMENT_DOWNLOAD_SECRET", "x" * 40)
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "x" * 40)
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS", 3600)
    monkeypatch.setattr(app_config, "DOCUMENT_RETENTION_HOURS", 24)
    monkeypatch.setattr(app_config, "CLEANUP_JOB_SECRET", "cleanup-secret-for-tests")
    monkeypatch.setattr(app_config, "CRON_SECRET", "cleanup-secret-for-tests")

    def verifier(token: str) -> AuthenticatedUser:
        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        if token == TOKEN_B:
            return AuthenticatedUser(user_id=USER_B)
        raise Exception("invalid")  # mapped by caller? verify_supabase raises via override

    def safe_verifier(token: str) -> AuthenticatedUser:
        from fastapi import HTTPException

        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        if token == TOKEN_B:
            return AuthenticatedUser(user_id=USER_B)
        raise HTTPException(status_code=401, detail="Authentication required.")

    set_token_verifier(safe_verifier)
    yield
    reset_token_verifier()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def misformatted_docx(tmp_path: Path) -> Path:
    path = tmp_path / "mis.docx"
    build_b_misformatted(path)
    return path


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload(client, path: Path, token: str, endpoint: str):
    return client.post(
        endpoint,
        data={"template_id": "apa7_student"},
        headers=_auth(token),
        files={
            "file": (
                path.name,
                path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )


def test_anonymous_analyze_rejected(client, misformatted_docx):
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        files={
            "file": (
                "mis.docx",
                misformatted_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 401


def test_anonymous_fix_rejected(client, misformatted_docx):
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        files={
            "file": (
                "mis.docx",
                misformatted_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 401


def test_invalid_token_rejected(client, misformatted_docx):
    response = _upload(
        client, misformatted_docx, "bogus-token", "/documents/analyze"
    )
    assert response.status_code == 401


def test_user_a_owns_document_user_b_cannot_download(client, misformatted_docx):
    fixed = _upload(client, misformatted_docx, TOKEN_A, "/documents/fix")
    assert fixed.status_code == 200
    payload = fixed.json()
    assert payload["verification"]["safe_issues_after"] == 0
    assert payload["fixed_file_path"].startswith(f"fixed/{USER_A}/")
    document_id = payload["document_id"]
    download_url = payload["download_url"]

    ok = client.get(download_url, headers=_auth(TOKEN_A))
    assert ok.status_code == 200
    assert ok.content[:2] == b"PK"
    assert "no-store" in ok.headers.get("Cache-Control", "")

    # User B with User A capability token still cannot load User A object.
    stolen = client.get(download_url, headers=_auth(TOKEN_B))
    assert stolen.status_code == 404

    # Anonymous cannot download.
    anon = client.get(download_url)
    assert anon.status_code == 401


def test_download_token_bound_to_user_and_expiry():
    document_id = str(uuid4())
    token = make_download_token(user_id=USER_A, document_id=document_id, ttl_seconds=60)
    verify_download_token(user_id=USER_A, document_id=document_id, token=token)

    with pytest.raises(Exception):
        verify_download_token(user_id=USER_B, document_id=document_id, token=token)

    other_doc = str(uuid4())
    with pytest.raises(Exception):
        verify_download_token(user_id=USER_A, document_id=other_doc, token=token)

    expired = make_download_token(
        user_id=USER_A,
        document_id=document_id,
        ttl_seconds=1,
        now=int(time.time()) - 10,
    )
    with pytest.raises(Exception):
        verify_download_token(
            user_id=USER_A,
            document_id=document_id,
            token=expired,
            now=int(time.time()),
        )


def test_retention_cleanup_deletes_expired_only(tmp_path, monkeypatch):
    from app.services.document_store import (
        StoredFixedObject,
        save_fixed_document,
        temp_fixed_path,
        list_fixed_objects,
    )

    doc_keep = str(uuid4())
    doc_expire = str(uuid4())
    src = tmp_path / "blob.docx"
    src.write_bytes(b"PK\x03\x04" + b"0" * 32)

    # Write via store API (monkeypatched FIXED_DIR).
    save_fixed_document(USER_A, doc_keep, src)
    save_fixed_document(USER_B, doc_expire, src)

    objects = list_fixed_objects()
    assert len(objects) == 2

    # Force one object to look expired.
    aged = []
    now = time.time()
    for obj in objects:
        if obj.document_id == doc_expire:
            aged.append(
                StoredFixedObject(
                    pathname=obj.pathname,
                    user_id=obj.user_id,
                    document_id=obj.document_id,
                    created_at=now - 48 * 3600,
                )
            )
        else:
            aged.append(obj)

    report = cleanup_expired_fixed_documents(
        retention_hours=24, now=now, objects=aged
    )
    assert report.deleted == 1
    assert report.expired == 1

    remaining = {o.document_id for o in list_fixed_objects()}
    assert doc_keep in remaining
    assert doc_expire not in remaining

    # Idempotent second run.
    report2 = cleanup_expired_fixed_documents(
        retention_hours=24, now=now, objects=aged
    )
    assert report2.deleted in (0, 1)


def test_cleanup_ignores_unrelated_paths():
    from app.services.document_store import StoredFixedObject

    now = time.time()
    junk = [
        StoredFixedObject(
            pathname="other/namespace/file.docx",
            user_id=USER_A,
            document_id=str(uuid4()),
            created_at=now - 99 * 3600,
        )
    ]
    report = cleanup_expired_fixed_documents(
        retention_hours=1, now=now, objects=junk
    )
    assert report.deleted == 0
    assert report.skipped == 1


def test_cleanup_endpoint_requires_secret(client):
    denied = client.post("/internal/cleanup-fixed-documents")
    assert denied.status_code == 401

    ok = client.post(
        "/internal/cleanup-fixed-documents",
        headers={"X-Cleanup-Secret": "cleanup-secret-for-tests"},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True


def test_production_secret_required(monkeypatch):
    monkeypatch.setattr(app_config, "IS_PRODUCTION", True)
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", None)
    with pytest.raises(RuntimeError):
        app_config.resolve_download_secret()

    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "short")
    with pytest.raises(RuntimeError):
        app_config.resolve_download_secret()

    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "y" * 32)
    secret = app_config.resolve_download_secret()
    assert len(secret) == 32
