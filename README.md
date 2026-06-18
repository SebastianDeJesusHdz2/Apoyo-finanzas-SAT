# Apoyo Finanzas SAT

Aplicacion de escritorio local para capturar recibos, importar CFDI XML, analizar imagenes con OCR y generar reportes financieros utiles para organizacion fiscal en Mexico.

## Funciones

- Registro local de recibos, facturas y CFDI en SQLite.
- Importacion de XML CFDI para extraer RFC, UUID, fecha, impuestos, forma/metodo de pago, uso CFDI y totales.
- OCR local opcional para sugerir datos desde fotos de recibos.
- Tabla con filtros por periodo, semana, mes, año, categoria, estatus y busqueda.
- Exportacion de reportes a CSV, Excel y PDF.
- Interfaz de escritorio oscura con transparencia y blur interno.

## Instalacion

Todo queda dentro de esta carpeta: entorno Python, base local, recibos, reportes y OCR opcional.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Para abrir la aplicacion:

```bash
.venv/bin/python main.py
```

## OCR

La app busca primero Tesseract local en `vendor/tesseract/`. Para instalarlo sin tocar el sistema:

```bash
bash scripts/install_local_tesseract.sh
```

Tambien puede usar Tesseract instalado en el sistema si el comando `tesseract` esta disponible en `PATH`.

## Datos locales

- Base SQLite: `data/db/pfinanzas.sqlite3`
- Imagenes de recibos: `data/receipts/`
- XML CFDI: `data/cfdi/`
- Reportes generados: `exports/`

Estas rutas estan ignoradas por Git para evitar subir informacion personal, comprobantes, XML fiscales, bases de datos, reportes, entornos virtuales y binarios locales.

## Pruebas

```bash
.venv/bin/python -m pytest -q
```

## Licencia

Apache License 2.0. Esta herramienta organiza informacion y genera reportes internos; no sustituye validacion directa ante el SAT ni asesoria contable.
