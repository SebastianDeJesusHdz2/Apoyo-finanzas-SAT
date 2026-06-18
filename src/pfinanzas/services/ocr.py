from __future__ import annotations

import re
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from pfinanzas.core.paths import LOCAL_TESSDATA_DIR, LOCAL_TESSERACT_BIN, LOCAL_TESSERACT_DIR


RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)
RFC_CANDIDATE_RE = re.compile(r"\b[A-ZÑ&]{3,4}[A-Z0-9]{6}[A-Z0-9]{3}\b", re.IGNORECASE)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
DATE_PATTERNS = [
    re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b"),
]
AMOUNT_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:[,\s][0-9]{3})*(?:[.,][0-9]{2})|[0-9]+(?:[.,][0-9]{2})?)")


def extract_text_from_image(path: str | Path) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("Falta instalar pytesseract en el entorno local.") from exc

    _configure_local_tesseract(pytesseract)

    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    if image.width < 1600:
        scale = max(2, round(1600 / max(image.width, 1)))
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    image = image.point(lambda pixel: 255 if pixel > 180 else 0)

    try:
        config = f'--tessdata-dir "{LOCAL_TESSDATA_DIR}"' if LOCAL_TESSDATA_DIR.exists() else ""
        return pytesseract.image_to_string(image, lang="spa+eng", config=config)
    except Exception as exc:  # pytesseract raises a custom error when the binary is absent.
        raise RuntimeError(
            "No pude ejecutar Tesseract. Instala tesseract-ocr y tesseract-ocr-spa en el sistema "
            "o captura el recibo manualmente."
        ) from exc


def _configure_local_tesseract(pytesseract_module) -> None:
    if not LOCAL_TESSERACT_BIN.exists():
        return

    pytesseract_module.pytesseract.tesseract_cmd = str(LOCAL_TESSERACT_BIN)
    lib_dir = LOCAL_TESSERACT_DIR / "usr" / "lib" / "x86_64-linux-gnu"
    if lib_dir.exists():
        current = os.environ.get("LD_LIBRARY_PATH", "")
        entries = [str(lib_dir), *([current] if current else [])]
        os.environ["LD_LIBRARY_PATH"] = ":".join(entries)


def analyze_image(path: str | Path) -> tuple[str, dict[str, object]]:
    text = extract_text_from_image(path)
    parsed = parse_receipt_text(text)
    parsed["raw_text"] = text
    return text, parsed


def parse_receipt_text(text: str) -> dict[str, object]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = "\n".join(lines)
    amounts_by_line = [(line, _amounts_in_line(line)) for line in lines]

    issuer_name = _guess_issuer(lines)
    rfcs = _find_rfcs(compact)
    uuid_match = UUID_RE.search(compact)
    subtotal = _find_labeled_amount(amounts_by_line, ("SUBTOTAL", "SUB TOTAL"))
    iva = _find_labeled_amount(amounts_by_line, ("IVA", "I.V.A"))
    total = _find_labeled_amount(amounts_by_line, ("TOTAL", "IMPORTE"))
    if total == 0:
        total = max(_all_amounts(amounts_by_line), default=0.0)

    parsed: dict[str, object] = {
        "document_type": "Recibo",
        "status": "por revisar",
        "issuer_name": issuer_name,
        "issuer_rfc": rfcs[0] if rfcs else "",
        "receiver_rfc": rfcs[1] if len(rfcs) > 1 else "",
        "date": _guess_date(compact),
        "category": _guess_category(compact),
        "description": "Recibo importado por OCR",
        "currency": "MXN",
        "subtotal": subtotal,
        "tax_iva": iva,
        "total": total,
        "uuid": uuid_match.group(0).upper() if uuid_match else "",
        "notes": "Datos sugeridos por OCR; revisar antes de marcar como validado.",
    }
    return parsed


def _guess_issuer(lines: list[str]) -> str:
    ignored = ("RFC", "TOTAL", "TICKET", "FECHA", "FACTURA", "IVA")
    for line in lines[:8]:
        if len(line) >= 3 and not any(token in line.upper() for token in ignored):
            return line[:120]
    return ""


def _find_rfcs(text: str) -> list[str]:
    found: list[str] = []
    for match in RFC_CANDIDATE_RE.finditer(text):
        normalized = _normalize_rfc(match.group(0))
        if RFC_RE.fullmatch(normalized) and normalized not in found:
            found.append(normalized)
    return found


def _normalize_rfc(value: str) -> str:
    cleaned = re.sub(r"[^A-ZÑ&0-9]", "", value.upper())
    if len(cleaned) not in (12, 13):
        return cleaned
    prefix_len = len(cleaned) - 9
    prefix = cleaned[:prefix_len]
    date_part = cleaned[prefix_len : prefix_len + 6]
    suffix = cleaned[prefix_len + 6 :]
    digit_fixes = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8"})
    return prefix + date_part.translate(digit_fixes) + suffix


def _guess_date(text: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = [int(part) for part in match.groups()]
        candidates: list[tuple[int, int, int]] = []
        if len(str(match.group(1))) == 4:
            candidates.append((parts[0], parts[1], parts[2]))
        else:
            year = parts[2] + 2000 if parts[2] < 100 else parts[2]
            candidates.append((year, parts[1], parts[0]))
            candidates.append((year, parts[0], parts[1]))
        for year, month, day in candidates:
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                continue
    return ""


def _amounts_in_line(line: str) -> list[float]:
    values = []
    for raw in AMOUNT_RE.findall(line):
        normalized = raw.replace(" ", "").replace(",", "")
        if normalized.count(".") == 0 and "," in raw:
            normalized = raw.replace(".", "").replace(",", ".")
        try:
            values.append(float(normalized))
        except ValueError:
            continue
    return values


def _find_labeled_amount(amounts_by_line: list[tuple[str, list[float]]], labels: tuple[str, ...]) -> float:
    for line, amounts in amounts_by_line:
        upper = line.upper()
        if any(label in upper for label in labels):
            if "SUB" not in labels[0] and "SUBTOTAL" in upper:
                continue
            if amounts:
                return amounts[-1]
    return 0.0


def _all_amounts(amounts_by_line: list[tuple[str, list[float]]]) -> list[float]:
    values: list[float] = []
    for _, amounts in amounts_by_line:
        values.extend(amounts)
    return values


def _guess_category(text: str) -> str:
    upper = text.upper()
    keyword_map = {
        "Combustible": ("GASOLINA", "PEMEX", "SHELL", "BP ", "GAS"),
        "Alimentos": ("RESTAURANTE", "CAFE", "CAFETERIA", "COMIDA", "OXXO", "SORIANA", "WALMART"),
        "Transporte": ("UBER", "DIDI", "TAXI", "AUTOBUS", "CASETA"),
        "Hospedaje": ("HOTEL", "HOSPEDAJE"),
        "Salud": ("FARMACIA", "HOSPITAL", "MEDICO"),
        "Telefonia e internet": ("TELCEL", "AT&T", "MOVISTAR", "INTERNET", "TELEFONO"),
        "Software": ("SOFTWARE", "MICROSOFT", "GOOGLE", "AWS", "OPENAI"),
    }
    for category, keywords in keyword_map.items():
        if any(keyword in upper for keyword in keywords):
            return category
    return "Sin categoria"
