# Campos fiscales contemplados

La app guarda campos comunes para organizar recibos y CFDI:

- Datos generales: tipo de documento, fecha, categoria, subcategoria, descripcion, estatus y notas.
- Emisor/receptor: nombre y RFC del emisor, nombre y RFC del receptor.
- CFDI: UUID, serie, folio, uso CFDI, regimen fiscal receptor, forma de pago, metodo de pago y moneda.
- Importes: subtotal, descuento, IVA trasladado, IVA retenido, ISR retenido y total.
- Evidencia: ruta de imagen del recibo y ruta de XML CFDI.

Para comprobantes fiscales mexicanos, el XML CFDI es la fuente mas confiable. Las fotos de recibos se procesan con OCR solo como apoyo y deben revisarse manualmente.
