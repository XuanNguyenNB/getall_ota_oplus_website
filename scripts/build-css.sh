#!/usr/bin/env bash
# Build the static UI stylesheet with the Tailwind v4 standalone CLI.
#
# No Node/npm required. Downloads the standalone binary to scripts/bin/ on
# first run (git-ignored), then compiles the Tailwind input into the served
# stylesheet. The output (src/ota_backend/static/styles.css) IS committed so
# the FastAPI app can serve it directly.
#
# Usage:
#   scripts/build-css.sh           # one-shot minified build
#   scripts/build-css.sh --watch   # rebuild on change (not minified)
#
# Pre-commit / CI contract
# ------------------------
# Whenever you edit ``tailwind.input.css``, ``index.html``, ``admin.html``,
# ``app.js``, ``admin.js`` or any file under ``static/modules/``, re-run this
# script and commit the rebuilt ``src/ota_backend/static/styles.css``. The CI
# job ``css-build-no-diff`` runs this script on Linux and fails if it produces
# a diff, so the committed CSS is guaranteed to match the input. We
# intentionally do NOT install husky or a pre-commit framework — this script
# is the single source of truth and can be wired into local git hooks
# manually if you want.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$REPO_ROOT/scripts/bin"
STATIC_DIR="$REPO_ROOT/src/ota_backend/static"
INPUT="$STATIC_DIR/tailwind.input.css"
OUTPUT="$STATIC_DIR/styles.css"
VERSION="v4.3.1"

case "$(uname -s)" in
  Linux*)  TARGET="tailwindcss-linux-x64" ;;
  Darwin*) [ "$(uname -m)" = "arm64" ] && TARGET="tailwindcss-macos-arm64" || TARGET="tailwindcss-macos-x64" ;;
  MINGW*|MSYS*|CYGWIN*) TARGET="tailwindcss-windows-x64.exe" ;;
  *) echo "Unsupported platform: $(uname -s)" >&2; exit 1 ;;
esac

case "$TARGET" in
  *.exe) BIN="$BIN_DIR/tailwindcss.exe" ;;
  *)     BIN="$BIN_DIR/tailwindcss" ;;
esac

if [ ! -x "$BIN" ]; then
  echo "Downloading Tailwind CLI $VERSION ($TARGET)..."
  mkdir -p "$BIN_DIR"
  curl -sLo "$BIN" "https://github.com/tailwindlabs/tailwindcss/releases/download/$VERSION/$TARGET"
  chmod +x "$BIN"
fi

if [ "${1:-}" = "--watch" ]; then
  exec "$BIN" -i "$INPUT" -o "$OUTPUT" --watch
fi

"$BIN" -i "$INPUT" -o "$OUTPUT" --minify
echo "Built $OUTPUT"
