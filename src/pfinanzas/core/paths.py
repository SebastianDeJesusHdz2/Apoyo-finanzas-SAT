from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = DATA_DIR / "db"
RECEIPTS_DIR = DATA_DIR / "receipts"
CFDI_DIR = DATA_DIR / "cfdi"
EXPORTS_DIR = PROJECT_ROOT / "exports"
DB_PATH = DB_DIR / "pfinanzas.sqlite3"
VENDOR_DIR = PROJECT_ROOT / "vendor"
LOCAL_TESSERACT_DIR = VENDOR_DIR / "tesseract"
LOCAL_TESSERACT_BIN = LOCAL_TESSERACT_DIR / "usr" / "bin" / "tesseract"
LOCAL_TESSDATA_DIR = LOCAL_TESSERACT_DIR / "usr" / "share" / "tesseract-ocr" / "5" / "tessdata"


def ensure_app_dirs() -> None:
    for path in (DATA_DIR, DB_DIR, RECEIPTS_DIR, CFDI_DIR, EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def to_project_relative(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def resolve_storage_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
