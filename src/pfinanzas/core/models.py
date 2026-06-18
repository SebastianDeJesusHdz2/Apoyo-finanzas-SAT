from __future__ import annotations

from dataclasses import dataclass
from datetime import date


MONEY_FIELDS = {
    "subtotal",
    "discount",
    "tax_iva",
    "tax_retained_iva",
    "tax_retained_isr",
    "total",
}


RECEIPT_FIELDS = [
    "id",
    "created_at",
    "updated_at",
    "document_type",
    "status",
    "issuer_name",
    "issuer_rfc",
    "receiver_name",
    "receiver_rfc",
    "date",
    "category",
    "subcategory",
    "description",
    "payment_method",
    "payment_form",
    "cfdi_use",
    "fiscal_regime",
    "currency",
    "subtotal",
    "discount",
    "tax_iva",
    "tax_retained_iva",
    "tax_retained_isr",
    "total",
    "uuid",
    "serie",
    "folio",
    "file_path",
    "xml_path",
    "notes",
    "raw_text",
]


EDITABLE_FIELDS = [field for field in RECEIPT_FIELDS if field not in {"id", "created_at", "updated_at"}]


DEFAULT_CATEGORIES = [
    "Sin categoria",
    "Alimentos",
    "Combustible",
    "Transporte",
    "Hospedaje",
    "Telefonia e internet",
    "Renta",
    "Servicios",
    "Papeleria",
    "Equipo",
    "Software",
    "Salud",
    "Honorarios",
    "Impuestos",
    "Otros",
]


STATUSES = [
    "por revisar",
    "validado",
    "deducible",
    "no deducible",
    "pagado",
    "cancelado",
]


DOCUMENT_TYPES = [
    "Recibo",
    "CFDI",
    "Factura",
    "Nota",
    "Gasto",
]


@dataclass(slots=True)
class ReceiptFilters:
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None
    text: str | None = None
    status: str | None = None
