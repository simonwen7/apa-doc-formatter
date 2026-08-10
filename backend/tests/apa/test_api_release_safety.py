"""API upload/download safety for commercial release (Phase 3B)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.download_auth import make_download_token
from app.services.document_store import save_fixed_document, temp_fixed_path
from tests.apa.golden_corpus.builders import build_b_misformatted


client = TestClient(app)


@pytest.fixture()
def misformatted_docx(tmp_path: Path) -> Path:
    path = tmp_path / "mis.docx"
    build_b_misformatted(path)
    return path


def test_analyze_rejects_empty_upload():
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        files={
            "file": (
                "empty.docx",
                b"",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400


def test_analyze_rejects_misleading_extension():
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
        files={"file": ("notes.txt", b"not a docx", "text/plain")},
    )
    assert response.status_code == 400


def test_analyze_rejects_non_zip_bytes():
    response = client.post(
        "/documents/analyze",
        data={"template_id": "apa7_student"},
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


def test_download_requires_token(misformatted_docx: Path, tmp_path: Path):
    document_id = str(uuid4())
    # Persist a fixed file as if Fix succeeded.
    fixed = tmp_path / "fixed.docx"
    fixed.write_bytes(misformatted_docx.read_bytes())
    save_fixed_document(document_id, fixed)

    bare = client.get(f"/documents/download/{document_id}")
    assert bare.status_code == 403

    bad = client.get(f"/documents/download/{document_id}?token=deadbeef")
    assert bad.status_code == 403

    ok = client.get(
        f"/documents/download/{document_id}?token={make_download_token(document_id)}"
    )
    assert ok.status_code == 200
    assert ok.content[:2] == b"PK"


def test_download_rejects_invalid_document_ids():
    response = client.get("/documents/download/not-a-uuid?token=abc")
    assert response.status_code == 400

    traversal = client.get(
        "/documents/download/%2e%2e%2f%2e%2e%2fetc%2fpasswd?token=abc"
    )
    # Encoded traversal still fails UUID validation (400) or routing (404).
    assert traversal.status_code in (400, 404)


def test_fix_returns_tokenized_download_url(misformatted_docx: Path):
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
    assert response.status_code == 200
    payload = response.json()
    assert payload["verification"]["verified"] is True
    assert "token=" in payload["download_url"]
    assert not str(payload.get("fixed_file_path", "")).startswith("/")
    document_id = payload["document_id"]
    token = make_download_token(document_id)
    assert token in payload["download_url"]

    # Round-trip download bytes reopen as DOCX.
    downloaded = client.get(payload["download_url"])
    assert downloaded.status_code == 200
    assert len(downloaded.content) > 1000
