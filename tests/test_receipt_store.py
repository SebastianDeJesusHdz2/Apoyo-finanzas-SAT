from pathlib import Path

from pfinanzas.core import db
from pfinanzas.core.db import ReceiptStore, init_db


def test_store_save_defaults_money_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    init_db()
    store = ReceiptStore()

    receipt_id = store.save(
        {
            "document_type": "Recibo",
            "date": "2026-06-18",
            "category": "Prueba",
            "description": "Registro temporal",
            "total": 116,
        }
    )

    saved = store.get(receipt_id)

    assert saved is not None
    assert saved["subtotal"] == 0
    assert saved["tax_iva"] == 0
    assert saved["total"] == 116
