#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_DIR="$ROOT/vendor/_deb"
TARGET="$ROOT/vendor/tesseract"

mkdir -p "$DEB_DIR" "$TARGET"
cd "$DEB_DIR"

apt-get download \
  tesseract-ocr \
  tesseract-ocr-spa \
  tesseract-ocr-eng \
  tesseract-ocr-osd \
  libtesseract5 \
  libleptonica6

for package in ./*.deb; do
  dpkg-deb -x "$package" "$TARGET"
done

export LD_LIBRARY_PATH="$TARGET/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
"$TARGET/usr/bin/tesseract" --version
