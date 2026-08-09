import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Vercel sets VERCEL=1 in production/preview function runtimes.
IS_VERCEL = os.getenv("VERCEL") == "1"

# Runtime workspace for python-docx temp reads/writes.
# On Vercel the deployment FS is read-only except /tmp.
if IS_VERCEL:
    RUNTIME_DIR = Path("/tmp/docformatter")
else:
    RUNTIME_DIR = BASE_DIR.parent / "storage"

UPLOADS_DIR = RUNTIME_DIR / "uploads"
FIXED_DIR = RUNTIME_DIR / "fixed"

# Private Vercel Blob is required when fixed files must survive across
# separate serverless invocations (fix -> download).
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
USE_BLOB_STORAGE = IS_VERCEL

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def ensure_runtime_dirs() -> None:
    """Create local/runtime directories lazily (never at import time)."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    FIXED_DIR.mkdir(parents=True, exist_ok=True)
