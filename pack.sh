#!/usr/bin/env bash
# pack.sh - zip the whole MiniQubes project (this folder) so you can copy it to another PC.
#   ./pack.sh        makes ~/miniqubes.tar.gz  (and ~/miniqubes.zip if 'zip' is installed)
# On the other PC:  tar xzf miniqubes.tar.gz && cd miniqubes && ./install.sh
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
NAME=$(basename "$HERE")
cd "$HERE/.."
rm -f "$HOME/$NAME.tar.gz" "$HOME/$NAME.zip"
tar czf "$HOME/$NAME.tar.gz" --exclude=__pycache__ --exclude='*.pyc' "$NAME"
echo "made $HOME/$NAME.tar.gz"
if command -v zip >/dev/null; then
  zip -qr "$HOME/$NAME.zip" "$NAME" -x '*/__pycache__/*' '*.pyc'
  echo "made $HOME/$NAME.zip"
fi
