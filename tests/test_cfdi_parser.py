from pathlib import Path

from pfinanzas.services.cfdi import parse_cfdi_xml


def test_parse_cfdi_xml(tmp_path: Path) -> None:
    xml = tmp_path / "cfdi.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0" Serie="A" Folio="10" Fecha="2026-06-18T12:00:00" FormaPago="03" MetodoPago="PUE" Moneda="MXN" SubTotal="100.00" Total="116.00">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="EMISOR SA DE CV" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="RECEPTOR SA DE CV" RegimenFiscalReceptor="612" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto Descripcion="Servicio profesional" ValorUnitario="100.00" Importe="100.00" ObjetoImp="02"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="16.00">
    <cfdi:Traslados>
      <cfdi:Traslado Base="100.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="16.00"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="123E4567-E89B-12D3-A456-426614174000" FechaTimbrado="2026-06-18T12:00:05"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""",
        encoding="utf-8",
    )

    parsed = parse_cfdi_xml(xml)

    assert parsed["document_type"] == "CFDI"
    assert parsed["issuer_rfc"] == "AAA010101AAA"
    assert parsed["receiver_rfc"] == "BBB010101BBB"
    assert parsed["date"] == "2026-06-18"
    assert parsed["tax_iva"] == 16.0
    assert parsed["total"] == 116.0
    assert parsed["uuid"] == "123E4567-E89B-12D3-A456-426614174000"
