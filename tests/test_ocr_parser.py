from pfinanzas.services.ocr import parse_receipt_text


def test_parse_receipt_text_extracts_basic_fields() -> None:
    parsed = parse_receipt_text(
        """
        CAFETERIA CENTRO
        RFC AAA010101AAA
        FECHA 18/06/2026
        SUBTOTAL $100.00
        IVA $16.00
        TOTAL $116.00
        """
    )

    assert parsed["issuer_name"] == "CAFETERIA CENTRO"
    assert parsed["issuer_rfc"] == "AAA010101AAA"
    assert parsed["date"] == "2026-06-18"
    assert parsed["category"] == "Alimentos"
    assert parsed["tax_iva"] == 16.0
    assert parsed["total"] == 116.0
