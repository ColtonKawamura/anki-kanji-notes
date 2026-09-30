#!/bin/bash
# Install updateKanji on macOS by symlinking it onto your PATH.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/updateKanji"

if [ ! -f "$SOURCE" ]; then
  echo "error: updateKanji not found in $SCRIPT_DIR" >&2
  exit 1
fi

chmod +x "$SOURCE"

TARGET_DIR="/usr/local/bin"
if [ ! -d "$TARGET_DIR" ] || [ ! -w "$TARGET_DIR" ]; then
  TARGET_DIR="$HOME/.local/bin"
  mkdir -p "$TARGET_DIR"
fi

TARGET="$TARGET_DIR/updateKanji"
ln -sf "$SOURCE" "$TARGET"
echo "Linked $TARGET -> $SOURCE"

case ":$PATH:" in
  *":$TARGET_DIR:"*)
    echo "You can now run: updateKanji"
    ;;
  *)
    echo
    echo "$TARGET_DIR is not on your PATH. Add it for zsh with:"
    echo "  echo 'export PATH=\"$TARGET_DIR:\$PATH\"' >> ~/.zshrc"
    echo "  source ~/.zshrc"
    ;;
esac
