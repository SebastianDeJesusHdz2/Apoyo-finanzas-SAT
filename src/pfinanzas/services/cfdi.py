from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _children_by_name(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child
    return None


def _money(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _date_only(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


def parse_cfdi_xml(path: str | Path) -> dict[str, object]:
    xml_path = Path(path)
    root = ET.parse(xml_path).getroot()
    if _local_name(root.tag) != "Comprobante":
        raise ValueError("El XML no parece ser un CFDI: falta el nodo Comprobante.")

    emisor = _first_descendant(root, "Emisor")
    receptor = _first_descendant(root, "Receptor")
    timbre = _first_descendant(root, "TimbreFiscalDigital")
    conceptos_node = _first_descendant(root, "Conceptos")
    conceptos = _children_by_name(conceptos_node if conceptos_node is not None else root, "Concepto")

    iva_trasladado = 0.0
    iva_retenido = 0.0
    isr_retenido = 0.0
    for tax in root.iter():
        if _local_name(tax.tag) == "Traslado" and tax.attrib.get("Impuesto") == "002":
            iva_trasladado += _money(tax.attrib.get("Importe"))
        if _local_name(tax.tag) == "Retencion":
            if tax.attrib.get("Impuesto") == "002":
                iva_retenido += _money(tax.attrib.get("Importe"))
            if tax.attrib.get("Impuesto") == "001":
                isr_retenido += _money(tax.attrib.get("Importe"))

    descriptions = [concept.attrib.get("Descripcion", "") for concept in conceptos]
    description = "; ".join([text for text in descriptions if text]).strip()
    if len(description) > 400:
        description = description[:397] + "..."

    data: dict[str, object] = {
        "document_type": "CFDI",
        "status": "validado",
        "issuer_name": emisor.attrib.get("Nombre", "") if emisor is not None else "",
        "issuer_rfc": emisor.attrib.get("Rfc", "") if emisor is not None else "",
        "receiver_name": receptor.attrib.get("Nombre", "") if receptor is not None else "",
        "receiver_rfc": receptor.attrib.get("Rfc", "") if receptor is not None else "",
        "date": _date_only(root.attrib.get("Fecha")),
        "category": "Sin categoria",
        "description": description,
        "payment_method": root.attrib.get("MetodoPago", ""),
        "payment_form": root.attrib.get("FormaPago", ""),
        "cfdi_use": receptor.attrib.get("UsoCFDI", "") if receptor is not None else "",
        "fiscal_regime": receptor.attrib.get("RegimenFiscalReceptor", "") if receptor is not None else "",
        "currency": root.attrib.get("Moneda", "MXN"),
        "subtotal": _money(root.attrib.get("SubTotal")),
        "discount": _money(root.attrib.get("Descuento")),
        "tax_iva": iva_trasladado,
        "tax_retained_iva": iva_retenido,
        "tax_retained_isr": isr_retenido,
        "total": _money(root.attrib.get("Total")),
        "uuid": timbre.attrib.get("UUID", "") if timbre is not None else "",
        "serie": root.attrib.get("Serie", ""),
        "folio": root.attrib.get("Folio", ""),
        "notes": "Datos importados desde XML CFDI.",
    }
    return data
