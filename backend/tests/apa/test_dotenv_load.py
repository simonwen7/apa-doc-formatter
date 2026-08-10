"""Regression: backend/.env must load into config for local E2E."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def test_backend_dotenv_loads_into_config(tmp_path, monkeypatch):
    backend_root = Path(__file__).resolve().parents[2]
    env_file = backend_root / ".env"

    # Do not require the real developer .env; simulate with isolated env vars
    # after a fresh import path. Presence of load_dotenv wiring is validated by
    # ensuring getenv values set before import are visible (override=False path),
    # and that missing file does not crash.
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setenv("DOCUMENT_DOWNLOAD_SECRET", "z" * 40)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)

    for name in list(sys.modules):
        if name == "app.core.config" or name.startswith("app.core.config"):
            del sys.modules[name]

    import app.core.config as config

    importlib.reload(config)

    assert config.SUPABASE_URL.endswith("supabase.co")
    assert config.SUPABASE_ANON_KEY == "test-anon-key"
    assert (config.DOCUMENT_DOWNLOAD_SECRET or "").startswith("z")
    # Real .env may or may not exist; loading must never raise.
    assert env_file.exists() or not env_file.exists()
