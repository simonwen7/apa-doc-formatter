"""API upload/download safety — Phase 3B + 3C auth updates."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth_deps import AuthenticatedUser, reset_token_verifier, set_token_verifier
from app.core import config as app_config
from app.main import app
from app.services import document_store
from app.services.download_auth import make_download_token
from tests.apa.golden_corpus.builders import build_b_misformatted

USER_A = "11111111-1111-4111-8111-111111111111"
TOKEN_A = "access-token-user-a"


@pytest.fixture(autouse=True)
def _auth_and_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "IS_PRODUCTION", False)
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(document_store, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(document_store, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(app_config, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(app_config, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "x" * 40)
    monkeypatch.setattr(app_config, "CLEANUP_JOB_SECRET", "cleanup-secret-for-tests")

    def verifier(token: str) -> AuthenticatedUser:
        from fastapi import HTTPException

        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        raise HTTPException(status_code=401, detail="Authentication required.")

    set_token_verifier(verifier)
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


def _headers():
    return {"Authorization": f"Bearer {TOKEN_A}"}


def test_analyze_rejects_empty_upload(client):
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={
            "file": (
                "empty.docx",
                b"",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400


def test_analyze_rejects_misleading_extension(client):
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={"file": ("notes.txt", b"not a docx", "text/plain")},
    )
    assert response.status_code == 400


def test_analyze_rejects_non_zip_bytes(client):
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={
            "file": (
                "fake.docx",
                b"not-a-zip-package",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert "valid" in response.json()["detail"].lower()


def test_download_requires_auth_and_token(client, misformatted_docx, tmp_path):
    document_id = str(uuid4())
    fixed = tmp_path / "fixed.docx"
    fixed.write_bytes(misformatted_docx.read_bytes())
    document_store.save_fixed_document(USER_A, document_id, fixed)

    bare = client.get(f"/documents/download/{document_id}")
    assert bare.status_code == 401

    no_token = client.get(
        f"/documents/download/{document_id}",
        headers=_headers(),
    )
    assert no_token.status_code == 404

    token = make_download_token(user_id=USER_A, document_id=document_id)
    ok = client.get(
        f"/documents/download/{document_id}?token={token}",
        headers=_headers(),
    )
    assert ok.status_code == 200
    assert ok.content[:2] == b"PK"


def test_download_rejects_invalid_document_ids(client):
    response = client.get(
        "/documents/download/not-a-uuid?token=abc",
        headers=_headers(),
    )
    assert response.status_code == 400

    traversal = client.get(
        "/documents/download/%2e%2e%2f%2e%2e%2fetc%2fpasswd?token=abc",
        headers=_headers(),
    )
    assert traversal.status_code in (400, 404)


def test_fix_returns_tokenized_download_url(client, misformatted_docx):
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={
            "file": (
                "mis.docx",
                misformatted_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["verification"]["verified"] is True
    assert "token=" in payload["download_url"]
    assert payload["fixed_file_path"].startswith(f"fixed/{USER_A}/")
    assert not str(payload.get("fixed_file_path", "")).startswith("/")

    downloaded = client.get(payload["download_url"], headers=_headers())
    assert downloaded.status_code == 200
    assert len(downloaded.content) > 1000


def test_fix_route_preserves_fixer_http_exception(client, misformatted_docx, monkeypatch):
    from fastapi import HTTPException

    def verification_failure(*_args, **_kwargs):
        raise HTTPException(
            status_code=500,
            detail=(
                "Formatting verification failed. Remaining auto-fixable issues "
                "were detected after fix; no downloadable file was produced."
            ),
        )

    monkeypatch.setattr(
        "app.api.routes_documents.fix_document_path",
        verification_failure,
    )

    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={
            "file": (
                "mis.docx",
                misformatted_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 500
    assert "verification failed" in response.json()["detail"].lower()


def test_fix_route_generic_error_on_unexpected_exception(client, misformatted_docx, monkeypatch):
    def unexpected_failure(*_args, **_kwargs):
        raise ValueError("sensitive internal traceback detail")

    monkeypatch.setattr(
        "app.api.routes_documents.fix_document_path",
        unexpected_failure,
    )

    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers=_headers(),
        files={
            "file": (
                "mis.docx",
                misformatted_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Unable to format this .docx file. The original upload was not changed."
    )
    assert "traceback" not in response.json()["detail"].lower()
