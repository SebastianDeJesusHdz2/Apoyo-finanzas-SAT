#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/apoyo-finanzas-sat"
DESKTOP_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$DESKTOP_DIR/apoyo-finanzas-sat.desktop"

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR"

cp -a "$ROOT/main.py" "$ROOT/pyproject.toml" "$ROOT/requirements.txt" "$ROOT/README.md" "$ROOT/LICENSE" "$INSTALL_DIR/"

rm -rf "$INSTALL_DIR/src" "$INSTALL_DIR/docs" "$INSTALL_DIR/scripts"
cp -a "$ROOT/src" "$ROOT/docs" "$ROOT/scripts" "$INSTALL_DIR/"

if [ ! -d "$INSTALL_DIR/.venv" ]; then
  cp -a "$ROOT/.venv" "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/python" -m pip install --no-build-isolation --no-deps -e "$INSTALL_DIR" >/dev/null

mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/exports" "$INSTALL_DIR/vendor"
if [ -d "$ROOT/data" ]; then
  cp -a --update=none "$ROOT/data/." "$INSTALL_DIR/data/"
fi
if [ -d "$ROOT/exports" ]; then
  cp -a --update=none "$ROOT/exports/." "$INSTALL_DIR/exports/"
fi
if [ -d "$ROOT/vendor/tesseract" ] && [ ! -d "$INSTALL_DIR/vendor/tesseract" ]; then
  mkdir -p "$INSTALL_DIR/vendor"
  cp -a "$ROOT/vendor/tesseract" "$INSTALL_DIR/vendor/tesseract"
fi

cat > "$INSTALL_DIR/run.sh" <<EOF_RUN
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$INSTALL_DIR"
cd "\$APP_DIR"
exec "\$APP_DIR/.venv/bin/python" "\$APP_DIR/main.py" "\$@"
EOF_RUN
chmod +x "$INSTALL_DIR/run.sh"

cat > "$INSTALL_DIR/icon.svg" <<'EOF_ICON'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="24" fill="#0b0f0e"/>
  <path d="M26 35h76v58H26z" rx="8" fill="#14231f"/>
  <path d="M36 48h56M36 64h34M36 80h48" stroke="#7bd6b4" stroke-width="8" stroke-linecap="round"/>
  <circle cx="93" cy="82" r="13" fill="#d0a05b"/>
  <path d="M89 82h8M93 78v8" stroke="#0b0f0e" stroke-width="4" stroke-linecap="round"/>
</svg>
EOF_ICON

cat > "$DESKTOP_FILE" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=Apoyo Finanzas SAT
Comment=Recibos, CFDI y reportes financieros locales
Exec=$INSTALL_DIR/run.sh
Icon=$INSTALL_DIR/icon.svg
Terminal=false
Categories=Office;Finance;
StartupNotify=true
EOF_DESKTOP
chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
  kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
fi

echo "$INSTALL_DIR"
echo "$DESKTOP_FILE"
