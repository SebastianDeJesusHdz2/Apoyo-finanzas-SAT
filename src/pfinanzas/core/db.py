from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pfinanzas.core.models import DEFAULT_CATEGORIES, EDITABLE_FIELDS, MONEY_FIELDS, ReceiptFilters
from pfinanzas.core.paths import DB_PATH, ensure_app_dirs


def connect() -> sqlite3.Connection:
    ensure_app_dirs()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path: Path = DB_PATH) -> None:
    ensure_app_dirs()
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'Recibo',
                status TEXT NOT NULL DEFAULT 'por revisar',
                issuer_name TEXT,
                issuer_rfc TEXT,
                receiver_name TEXT,
                receiver_rfc TEXT,
                date TEXT,
                category TEXT NOT NULL DEFAULT 'Sin categoria',
                subcategory TEXT,
                description TEXT,
                payment_method TEXT,
                payment_form TEXT,
                cfdi_use TEXT,
                fiscal_regime TEXT,
                currency TEXT NOT NULL DEFAULT 'MXN',
                subtotal REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                tax_iva REAL NOT NULL DEFAULT 0,
                tax_retained_iva REAL NOT NULL DEFAULT 0,
                tax_retained_isr REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                uuid TEXT,
                serie TEXT,
                folio TEXT,
                file_path TEXT,
                xml_path TEXT,
                notes TEXT,
                raw_text TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                name TEXT PRIMARY KEY
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO categories(name) VALUES (?)",
            [(category,) for category in DEFAULT_CATEGORIES],
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_category ON receipts(category)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_uuid ON receipts(uuid)")
        connection.commit()


class ReceiptStore:
    def list_categories(self) -> list[str]:
        with connect() as connection:
            rows = connection.execute("SELECT name FROM categories ORDER BY name").fetchall()
        return [row["name"] for row in rows]

    def ensure_category(self, category: str | None) -> None:
        if not category:
            return
        with connect() as connection:
            connection.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (category.strip(),))
            connection.commit()

    def save(self, values: dict[str, Any]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        clean = {field: values.get(field) for field in EDITABLE_FIELDS}
        clean["category"] = clean.get("category") or "Sin categoria"
        clean["document_type"] = clean.get("document_type") or "Recibo"
        clean["status"] = clean.get("status") or "por revisar"
        clean["currency"] = clean.get("currency") or "MXN"
        for field in MONEY_FIELDS:
            value = clean.get(field)
            if value in (None, ""):
                clean[field] = 0.0
                continue
            try:
                clean[field] = float(value)
            except (TypeError, ValueError):
                clean[field] = 0.0
        self.ensure_category(str(clean["category"]))

        receipt_id = values.get("id")
        with connect() as connection:
            if receipt_id:
                update_values = {**clean, "updated_at": now, "id": int(receipt_id)}
                update_fields = [*clean.keys(), "updated_at"]
                assignments = ", ".join([f"{field} = :{field}" for field in update_fields])
                connection.execute(
                    f"UPDATE receipts SET {assignments} WHERE id = :id",
                    update_values,
                )
                saved_id = int(receipt_id)
            else:
                insert_values = {**clean, "created_at": now, "updated_at": now}
                fields = ["created_at", "updated_at", *EDITABLE_FIELDS]
                placeholders = ", ".join([f":{field}" for field in fields])
                connection.execute(
                    f"INSERT INTO receipts ({', '.join(fields)}) VALUES ({placeholders})",
                    insert_values,
                )
                saved_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.commit()
        return saved_id

    def get(self, receipt_id: int) -> dict[str, Any] | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        return dict(row) if row else None

    def delete(self, receipt_id: int) -> None:
        with connect() as connection:
            connection.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
            connection.commit()

    def list(self, filters: ReceiptFilters | None = None) -> list[dict[str, Any]]:
        where, params = self._where(filters)
        query = f"""
            SELECT *
            FROM receipts
            {where}
            ORDER BY COALESCE(date, '' ) DESC, id DESC
        """
        with connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def totals(self, filters: ReceiptFilters | None = None) -> dict[str, float]:
        where, params = self._where(filters)
        query = f"""
            SELECT
                COUNT(*) AS count,
                COALESCE(SUM(subtotal), 0) AS subtotal,
                COALESCE(SUM(tax_iva), 0) AS tax_iva,
                COALESCE(SUM(tax_retained_iva), 0) AS tax_retained_iva,
                COALESCE(SUM(tax_retained_isr), 0) AS tax_retained_isr,
                COALESCE(SUM(total), 0) AS total
            FROM receipts
            {where}
        """
        with connect() as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row)

    def _where(self, filters: ReceiptFilters | None) -> tuple[str, dict[str, Any]]:
        if filters is None:
            return "", {}

        clauses: list[str] = []
        params: dict[str, Any] = {}
        if filters.date_from:
            clauses.append("date >= :date_from")
            params["date_from"] = filters.date_from.isoformat()
        if filters.date_to:
            clauses.append("date <= :date_to")
            params["date_to"] = filters.date_to.isoformat()
        if filters.category and filters.category != "Todas":
            clauses.append("category = :category")
            params["category"] = filters.category
        if filters.status and filters.status != "Todos":
            clauses.append("status = :status")
            params["status"] = filters.status
        if filters.text:
            clauses.append(
                """
                (
                    issuer_name LIKE :text OR issuer_rfc LIKE :text OR receiver_rfc LIKE :text
                    OR description LIKE :text OR uuid LIKE :text OR notes LIKE :text
                )
                """
            )
            params["text"] = f"%{filters.text.strip()}%"

        if not clauses:
            return "", {}
        return "WHERE " + " AND ".join(clauses), params
