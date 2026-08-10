"""Regression: official vercel.blob.BlobClient + BLOB_READ_WRITE_TOKEN."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth_deps import AuthenticatedUser, reset_token_verifier, set_token_verifier
from app.core import config as app_config
from app.core.config import DOCX_MEDIA_TYPE
from app.main import app
from app.services import document_store
from app.services.document_store import (
    BLOB_AUTH_FAILED,
    BlobStorageError,
    StoredFixedObject,
    require_blob_rw_token,
)
from app.services.retention_cleanup import cleanup_expired_fixed_documents

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
TOKEN_A = "access-token-user-a"
TOKEN_B = "access-token-user-b"
FAKE_RW = "vercel_blob_rw_storeTEST_fake-secret-value"


@dataclass
class _FakePutResult:
    pathname: str
    url: str = ""
    download_url: str = ""
    content_type: str = ""
    content_disposition: str = ""


@dataclass
class _FakeGetResult:
    content: bytes
    pathname: str = ""
    url: str = ""
    download_url: str = ""
    content_type: str = "application/octet-stream"
    size: int = 0
    content_disposition: str = ""
    cache_control: str = ""
    uploaded_at: datetime | None = None
    etag: str = ""
    status_code: int = 200


@dataclass
class _FakeListItem:
    pathname: str
    url: str = ""
    download_url: str = ""
    size: int = 1
    uploaded_at: datetime | None = None


@dataclass
class _FakeListResult:
    blobs: list[_FakeListItem]
    cursor: str | None = None
    has_more: bool = False
    folders: list[str] | None = None


class FakeBlobClient:
    """In-memory stand-in for vercel.blob.BlobClient."""

    instances: list["FakeBlobClient"] = []

    def __init__(self, token: str | None = None):
        self.token_arg = token
        self.puts: list[dict] = []
        self.gets: list[dict] = []
        self.deletes: list[str] = []
        self.lists: list[dict] = []
        self.objects: dict[str, bytes] = {}
        FakeBlobClient.instances.append(self)

    def put(self, path, body, *, access="public", content_type=None, add_random_suffix=False, overwrite=False, **kwargs):
        self.puts.append(
            {
                "path": path,
                "body": body,
                "access": access,
                "content_type": content_type,
                "add_random_suffix": add_random_suffix,
                "overwrite": overwrite,
                "kwargs": kwargs,
            }
        )
        self.objects[path] = bytes(body)
        return _FakePutResult(pathname=path, content_type=content_type or "")

    def get(self, url_or_path, *, access="public", **kwargs):
        self.gets.append({"path": url_or_path, "access": access, "kwargs": kwargs})
        if url_or_path not in self.objects:
            from vercel.blob.errors import BlobNotFoundError

            raise BlobNotFoundError()
        return _FakeGetResult(content=self.objects[url_or_path], pathname=url_or_path)

    def list_objects(self, *, prefix=None, cursor=None, limit=None, **kwargs):
        self.lists.append({"prefix": prefix, "cursor": cursor, "limit": limit})
        items = [
            _FakeListItem(
                pathname=path,
                uploaded_at=datetime.now(timezone.utc),
            )
            for path in sorted(self.objects)
            if prefix is None or path.startswith(prefix)
        ]
        return _FakeListResult(blobs=items)

    def delete(self, url_or_path, **kwargs):
        paths = [url_or_path] if isinstance(url_or_path, str) else list(url_or_path)
        for path in paths:
            self.deletes.append(path)
            self.objects.pop(path, None)


@pytest.fixture(autouse=True)
def _auth(monkeypatch, tmp_path):
    FakeBlobClient.instances.clear()
    monkeypatch.setattr(app_config, "IS_PRODUCTION", False)
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    monkeypatch.setattr(document_store, "FIXED_DIR", tmp_path / "fixed")
    monkeypatch.setattr(document_store, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(app_config, "DOCUMENT_DOWNLOAD_SECRET", "x" * 40)

    def verifier(token: str) -> AuthenticatedUser:
        from fastapi import HTTPException

        if token == TOKEN_A:
            return AuthenticatedUser(user_id=USER_A)
        if token == TOKEN_B:
            return AuthenticatedUser(user_id=USER_B)
        raise HTTPException(status_code=401, detail="Authentication required.")

    set_token_verifier(verifier)
    yield
    reset_token_verifier()


@pytest.fixture
def blob_mode(monkeypatch):
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", FAKE_RW)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)

    shared = FakeBlobClient()

    def factory():
        require_blob_rw_token()
        return shared

    monkeypatch.setattr(document_store, "_blob_client", factory)
    return shared


def test_blob_put_uses_official_python_sdk(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"0" * 20)
    doc_id = str(uuid4())
    path = document_store.save_fixed_document(USER_A, doc_id, src)
    assert path == f"fixed/{USER_A}/{doc_id}.docx"
    assert any(p["path"] == path and p["access"] == "private" for p in blob_mode.puts)


def test_blob_put_is_private(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"0" * 20)
    document_store.save_fixed_document(USER_A, str(uuid4()), src)
    assert blob_mode.puts
    assert all(p["access"] == "private" for p in blob_mode.puts)


def test_blob_get_uses_official_python_sdk(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    payload = b"PK\x03\x04" + b"1" * 20
    src.write_bytes(payload)
    doc_id = str(uuid4())
    document_store.save_fixed_document(USER_A, doc_id, src)
    content, filename = document_store.load_fixed_document(USER_A, doc_id)
    assert content == payload
    assert filename == f"{doc_id}.docx"
    assert any(
        g["path"] == f"fixed/{USER_A}/{doc_id}.docx" and g["access"] == "private"
        for g in blob_mode.gets
    )


def test_blob_list_uses_official_python_sdk(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"2" * 20)
    doc_id = str(uuid4())
    document_store.save_fixed_document(USER_A, doc_id, src)
    objects = document_store.list_fixed_objects()
    assert any(o.document_id == doc_id for o in objects)
    assert any(lst["prefix"] == "fixed/" for lst in blob_mode.lists)


def test_blob_delete_uses_official_python_sdk(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"3" * 20)
    doc_id = str(uuid4())
    document_store.save_fixed_document(USER_A, doc_id, src)
    assert document_store.delete_fixed_document(USER_A, doc_id) is True
    assert f"fixed/{USER_A}/{doc_id}.docx" in blob_mode.deletes
    assert f"fixed/{USER_A}/{doc_id}.meta.json" in blob_mode.deletes


def test_blob_token_not_returned(tmp_path, monkeypatch, blob_mode):
    from tests.apa.golden_corpus.builders import build_b_misformatted

    # Exercise API with local storage so Fix succeeds without depending on fake put twice.
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers={"Authorization": f"Bearer {TOKEN_A}"},
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                DOCX_MEDIA_TYPE,
            )
        },
    )
    assert response.status_code == 200
    assert FAKE_RW not in response.text
    assert "BLOB_READ_WRITE_TOKEN" not in response.text
    assert response.json()["fixed_file_path"].startswith(f"fixed/{USER_A}/")


def test_blob_token_not_logged(blob_mode, caplog, tmp_path, monkeypatch):
    import logging

    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"4" * 20)

    def boom():
        raise RuntimeError(f"provider rejected token={FAKE_RW}")

    monkeypatch.setattr(document_store, "_blob_client", boom)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(Exception):
            document_store.save_fixed_document(USER_A, str(uuid4()), src)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert FAKE_RW not in joined
    assert "BLOB_WRITE_FAILED" in joined or "BLOB_AUTH_FAILED" in joined


def test_missing_blob_token_fails_safely(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", True)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"5" * 20)
    with pytest.raises(Exception) as exc_info:
        document_store.save_fixed_document(USER_A, str(uuid4()), src)
    # HTTPException 503 for API layer path
    assert getattr(exc_info.value, "status_code", None) == 503
    assert FAKE_RW not in str(exc_info.value)
    with pytest.raises(BlobStorageError) as auth_exc:
        require_blob_rw_token()
    assert auth_exc.value.category == BLOB_AUTH_FAILED


def test_owner_namespaced_path_unchanged(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"6" * 20)
    doc_id = str(uuid4())
    path = document_store.save_fixed_document(USER_A, doc_id, src)
    assert path == f"fixed/{USER_A}/{doc_id}.docx"


def test_supabase_auth_still_required(tmp_path):
    from tests.apa.golden_corpus.builders import build_b_misformatted

    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    response = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                DOCX_MEDIA_TYPE,
            )
        },
    )
    assert response.status_code == 401


def test_cross_user_isolation_unchanged(tmp_path, monkeypatch):
    from app.services.download_auth import make_download_token
    from tests.apa.golden_corpus.builders import build_b_misformatted

    monkeypatch.setattr(document_store, "USE_BLOB_STORAGE", False)
    client = TestClient(app)
    doc = tmp_path / "mis.docx"
    build_b_misformatted(doc)
    fix = client.post(
        "/documents/fix",
        data={"template_id": "apa7_student"},
        headers={"Authorization": f"Bearer {TOKEN_A}"},
        files={
            "file": (
                "mis.docx",
                doc.read_bytes(),
                DOCX_MEDIA_TYPE,
            )
        },
    )
    assert fix.status_code == 200
    document_id = fix.json()["document_id"]
    # User B with a forged owner-bound token for A's document must fail verify or 404.
    stolen = make_download_token(user_id=USER_A, document_id=document_id)
    denied = client.get(
        f"/documents/download/{document_id}?token={stolen}",
        headers={"Authorization": f"Bearer {TOKEN_B}"},
    )
    assert denied.status_code in {401, 403, 404}


def test_cleanup_uses_sdk_blob_path(blob_mode, tmp_path):
    src = tmp_path / "f.docx"
    src.write_bytes(b"PK\x03\x04" + b"7" * 20)
    doc_keep = str(uuid4())
    doc_expire = str(uuid4())
    document_store.save_fixed_document(USER_A, doc_keep, src)
    document_store.save_fixed_document(USER_B, doc_expire, src)

    import time

    now = time.time()
    objects = [
        StoredFixedObject(
            pathname=f"fixed/{USER_A}/{doc_keep}.docx",
            user_id=USER_A,
            document_id=doc_keep,
            created_at=now,
        ),
        StoredFixedObject(
            pathname=f"fixed/{USER_B}/{doc_expire}.docx",
            user_id=USER_B,
            document_id=doc_expire,
            created_at=now - 48 * 3600,
        ),
    ]
    report = cleanup_expired_fixed_documents(
        retention_hours=24, now=now, objects=objects
    )
    assert report.expired >= 1
    assert report.deleted >= 1
    assert any(doc_expire in p for p in blob_mode.deletes)
    assert not any(doc_keep in p for p in blob_mode.deletes)


def test_download_uses_sdk_private_read(blob_mode, tmp_path):
    from app.services.download_auth import make_download_token

    src = tmp_path / "f.docx"
    payload = b"PK\x03\x04" + b"8" * 20
    src.write_bytes(payload)
    doc_id = str(uuid4())
    document_store.save_fixed_document(USER_A, doc_id, src)
    token = make_download_token(user_id=USER_A, document_id=doc_id)
    client = TestClient(app)
    response = client.get(
        f"/documents/download/{doc_id}?token={token}",
        headers={"Authorization": f"Bearer {TOKEN_A}"},
    )
    assert response.status_code == 200
    assert response.content == payload
    assert "private" in response.headers.get("cache-control", "")
    assert FAKE_RW not in response.text
    assert any(g["access"] == "private" for g in blob_mode.gets)
