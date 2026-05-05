from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STORAGE_DIR = BASE_DIR.parent / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
FIXED_DIR = STORAGE_DIR / "fixed"
