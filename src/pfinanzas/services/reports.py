from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = [
    ("id", "ID"),
    ("date", "Fecha"),
    ("category", "Categoria"),
    ("status", "Estatus"),
    ("document_type", "Tipo"),
    ("issuer_name", "Emisor"),
    ("issuer_rfc", "RFC emisor"),
    ("receiver_rfc", "RFC receptor"),
    ("description", "Descripcion"),
    ("payment_form", "Forma pago"),
    ("payment_method", "Metodo pago"),
    ("cfdi_use", "Uso CFDI"),
    ("currency", "Moneda"),
    ("subtotal", "Subtotal"),
    ("discount", "Descuento"),
    ("tax_iva", "IVA"),
    ("tax_retained_iva", "IVA retenido"),
    ("tax_retained_isr", "ISR retenido"),
    ("total", "Total"),
    ("uuid", "UUID"),
    ("serie", "Serie"),
    ("folio", "Folio"),
    ("file_path", "Archivo imagen"),
    ("xml_path", "Archivo XML"),
    ("notes", "Notas"),
]


def export_csv(records: Iterable[dict], path: str | Path) -> Path:
    output = Path(path)
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[label for _, label in REPORT_COLUMNS])
        writer.writeheader()
        for record in records:
            writer.writerow(_labeled_record(record))
    return output


def export_xlsx(records: Iterable[dict], path: str | Path) -> Path:
    import pandas as pd

    output = Path(path)
    rows = [_labeled_record(record) for record in records]
    frame = pd.DataFrame(rows)
    summary_category = _summary_by(records=rows, key="Categoria")
    summary_month = _summary_by_month(rows)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Recibos", index=False)
        pd.DataFrame(summary_category).to_excel(writer, sheet_name="Por categoria", index=False)
        pd.DataFrame(summary_month).to_excel(writer, sheet_name="Por mes", index=False)
    return output


def export_pdf(records: Iterable[dict], path: str | Path, title: str = "Reporte PFinanzas") -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = Path(path)
    rows = list(records)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(output), pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Spacer(1, 0.15 * inch),
    ]

    totals = _totals(rows)
    story.append(
        Paragraph(
            f"Registros: {len(rows)} | Subtotal: ${totals['subtotal']:,.2f} | IVA: ${totals['tax_iva']:,.2f} | Total: ${totals['total']:,.2f}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    table_rows = [["Fecha", "Categoria", "Emisor", "RFC", "Descripcion", "Subtotal", "IVA", "Total", "UUID"]]
    for record in rows[:80]:
        table_rows.append(
            [
                str(record.get("date") or ""),
                str(record.get("category") or ""),
                _short(record.get("issuer_name"), 28),
                str(record.get("issuer_rfc") or ""),
                _short(record.get("description"), 34),
                _money(record.get("subtotal")),
                _money(record.get("tax_iva")),
                _money(record.get("total")),
                _short(record.get("uuid"), 18),
            ]
        )
    if len(rows) > 80:
        table_rows.append(["", "", "", "", f"Se omitieron {len(rows) - 80} registros en esta vista PDF.", "", "", "", ""])

    table = Table(table_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return output


def _labeled_record(record: dict) -> dict[str, object]:
    return {label: record.get(key, "") for key, label in REPORT_COLUMNS}


def _summary_by(records: list[dict], key: str) -> list[dict]:
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"Registros": 0, "Subtotal": 0.0, "IVA": 0.0, "Total": 0.0})
    for record in records:
        bucket = buckets[str(record.get(key) or "Sin valor")]
        bucket["Registros"] += 1
        bucket["Subtotal"] += float(record.get("Subtotal") or 0)
        bucket["IVA"] += float(record.get("IVA") or 0)
        bucket["Total"] += float(record.get("Total") or 0)
    return [{key: name, **values} for name, values in sorted(buckets.items())]


def _summary_by_month(records: list[dict]) -> list[dict]:
    for record in records:
        date_value = str(record.get("Fecha") or "")
        record["Mes"] = date_value[:7] if len(date_value) >= 7 else "Sin fecha"
    return _summary_by(records, "Mes")


def _totals(records: list[dict]) -> dict[str, float]:
    return {
        "subtotal": sum(float(record.get("subtotal") or 0) for record in records),
        "tax_iva": sum(float(record.get("tax_iva") or 0) for record in records),
        "total": sum(float(record.get("total") or 0) for record in records),
    }


def _money(value: object) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _short(value: object, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 3] + "..."
