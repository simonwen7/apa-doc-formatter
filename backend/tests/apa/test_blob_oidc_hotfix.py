"""Regression: Vercel Function runtime OIDC for Private Blob (hotfix)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from app.api.auth_deps import AuthenticatedUser, reset_token_verifier, set_token_verifier
from app.core import config as app_config
from app.main import app
from app.services import document_store
from app.services.document_store import _resolve_blob_auth, _resolve_oidc_token
from app.services.vercel_oidc import extract_vercel_oidc_token

USER_A = "11111111-1111-4111-8111-111111111111"
TOKEN_A = "access-token-user-a"
INFRA_OIDC = "vercel-runtime-oidc-token-value"


@pytest.fixture(autouse=True)
def _auth(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "IS_PRODUCTION", False)
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(document_store, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(document_store, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "x" * 40)

    def verifier(token: str) -> AuthenticatedUser:
        from fastapi import HTTPException

        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        raise HTTPException(status_code=401, detail="Authentication required.")

    set_token_verifier(verifier)
    yield
    reset_token_verifier()


def _make_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/documents/fix",
        "raw_path": b"/documents/fix",
        "query_string": b"",
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in headers.items()
        ],
        "client": ("127.0.0.1", 123),
        "server": ("test", 443),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return StarletteRequest(scope, receive)


def test_extract_vercel_oidc_ignores_supabase_authorization():
    request = _make_request(
        {
            "Authorization": "Bearer supabase-user-jwt",
            "x-vercel-oidc-token": INFRA_OIDC,
        }
    )
    assert extract_vercel_oidc_token(request) == INFRA_OIDC

    no_oidc = _make_request({"Authorization": "Bearer supabase-user-jwt"})
    assert extract_vercel_oidc_token(no_oidc) is None


def test_resolve_oidc_prefers_explicit_request_token_over_env(monkeypatch):
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "stale-env-oidc-token")

    def boom():
        raise RuntimeError("context unavailable")

    monkeypatch.setattr(
        "vercel.oidc.get_vercel_oidc_token_sync",
        boom,
        raising=False,
    )
    # Even if SDK fails, explicit request token wins.
    assert _resolve_oidc_token(oidc_token=INFRA_OIDC) == INFRA_OIDC


def test_resolve_oidc_does_not_prefer_env_before_explicit(monkeypatch):
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "stale-env-oidc-token")
    assert _resolve_oidc_token(oidc_token=INFRA_OIDC) == INFRA_OIDC
    assert _resolve_oidc_token(oidc_token=INFRA_OIDC) != "stale-env-oidc-token"


def test_blob_auth_uses_explicit_oidc_with_store_id(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("BLOB_STORE_ID", "store_abc123")
    monkeypatch.setattr(document_store, "_resolve_store_id", lambda: "abc123")

    auth = _resolve_blob_auth(oidc_token=INFRA_OIDC)
    assert auth.mode == "oidc"
    assert auth.token == INFRA_OIDC
    assert auth.store_id == "abc123"


def test_save_fixed_passes_oidc_into_blob_resolver(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    captured: dict = {}

    def fake_resolve(*, oidc_token=None):
        captured["oidc_token"] = oidc_token
        return document_store._BlobAuth(
            token=oidc_token or "missing",
            store_id="abc",
            mode="oidc",
        )

    monkeypatch.setattr(document_store, "_resolve_blob_auth", fake_resolve)
    monkeypatch.setattr(document_store, "_put_private_blob", lambda *a, **k: None)

    # Avoid real meta put network
    def fake_save(user_id, document_id, source_path, created_at, *, oidc_token=None):
        auth = document_store._resolve_blob_auth(oidc_token=oidc_token)
        captured["auth_token"] = auth.token
        return document_store.fixed_pathname(user_id, document_id)

    monkeypatch.setattr(document_store, "_save_fixed_to_blob", fake_save)

    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"0" * 20)
    doc_id = str(uuid4())
    path = document_store.save_fixed_document(
        USER_A, doc_id, src, oidc_token=INFRA_OIDC
    )
    assert path.startswith(f"fixed/{USER_A}/")
    assert captured["oidc_token"] == INFRA_OIDC
    assert captured["auth_token"] == INFRA_OIDC


def test_fix_response_never_contains_oidc_token(tmp_path, monkeypatch):
    from tests.apa.golden_corpus.builders import build_b_misformatted

    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers={
            "Authorization": f"Bearer {TOKEN_A}",
            "x-vercel-oidc-token": INFRA_OIDC,
        },
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    body = response.text
    assert INFRA_OIDC not in body
    assert "x-vercel-oidc-token" not in body.lower()
    payload = response.json()
    assert payload["fixed_file_path"].startswith(f"fixed/{USER_A}/")
    assert payload["verification"]["safe_issues_after"] == 0


def test_fix_still_requires_supabase_auth(tmp_path):
    from tests.apa.golden_corpus.builders import build_b_misformatted

    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers={"x-vercel-oidc-token": INFRA_OIDC},
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 401


def test_fix_propagates_runtime_oidc_header_to_storage(tmp_path, monkeypatch):
    from tests.apa.golden_corpus.builders import build_b_misformatted

    captured: dict = {}

    def fake_save(user_id, document_id, source_path, *, oidc_token=None):
        captured["oidc_token"] = oidc_token
        captured["path"] = f"fixed/{user_id}/{document_id}.docx"
        return captured["path"]

    import app.api.routes_documents as routes_documents

    monkeypatch.setattr(routes_documents, "save_fixed_document", fake_save)
    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers={
            "Authorization": f"Bearer {TOKEN_A}",
            "x-vercel-oidc-token": INFRA_OIDC,
        },
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    assert captured["oidc_token"] == INFRA_OIDC
    assert captured["path"].startswith(f"fixed/{USER_A}/")
    assert INFRA_OIDC not in response.text


def test_missing_runtime_oidc_fails_safely_without_leaking_secrets(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.setattr(document_store, "_resolve_store_id", lambda: "abc123")

    def boom():
        raise RuntimeError("no context")

    monkeypatch.setattr(
        "vercel.oidc.get_vercel_oidc_token_sync",
        boom,
        raising=False,
    )

    with pytest.raises(RuntimeError) as exc_info:
        _resolve_blob_auth(oidc_token=None)

    message = str(exc_info.value)
    assert "x-vercel-oidc-token" in message
    assert INFRA_OIDC not in message


def test_log_blob_failure_never_includes_token(caplog):
    import logging

    with caplog.at_level(logging.ERROR):
        document_store._log_blob_failure(
            "put",
            RuntimeError(f"auth failed token={INFRA_OIDC}"),
        )
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert INFRA_OIDC not in joined
    assert "RuntimeError" in joined
