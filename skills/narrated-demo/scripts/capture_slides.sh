#!/usr/bin/env bash
# Screenshot every NN-*.html slide in a directory to NN-*.png at 1920x1080.
#
# Usage: capture_slides.sh <slides_dir> <frames_dir>
#
# Uses agent-browser if available (https://github.com/…/agent-browser); otherwise
# falls back to headless Chrome/Chromium. Set BROWSER_BIN to force a specific
# Chrome binary for the fallback.
set -uo pipefail   # NOT -e: a single slide failing must not abort the batch
shopt -s nullglob  # an empty glob expands to nothing, not the literal pattern
SLIDES="${1:?slides_dir}"; FRAMES="${2:?frames_dir}"
mkdir -p "$FRAMES"

to_url() {  # absolute path -> file:// URL (resolves MSYS /tmp etc. to real paths)
  local dir base p
  # pwd -W (git-bash/MSYS) yields a native Windows path (C:/...); fall back to pwd.
  dir="$(cd "$(dirname "$1")" 2>/dev/null && { pwd -W 2>/dev/null || pwd; })"
  base="$(basename "$1")"
  p="$dir/$base"
  case "$p" in
    [A-Za-z]:/*) echo "file:///$p" ;;                # C:/x  -> file:///C:/x  (Windows)
    /[A-Za-z]/*) echo "file:///${p:1:1}:${p:2}" ;;   # /c/x  -> file:///c:/x  (git-bash mount)
    *)           echo "file://$p" ;;                 # /home/x -> file:///home/x  (unix)
  esac
}

if command -v agent-browser >/dev/null 2>&1; then
  agent-browser set viewport 1920 1080 >/dev/null 2>&1 || true
  n=0
  for f in "$SLIDES"/[0-9][0-9]-*.html; do
    name="$(basename "$f" .html)"
    agent-browser open "$(to_url "$f")" >/dev/null 2>&1 || true
    sleep 1.1
    agent-browser screenshot "$FRAMES/$name.png" >/dev/null 2>&1 || true
    [ -s "$FRAMES/$name.png" ] && { echo "captured $name"; n=$((n+1)); } \
      || echo "WARN: failed $name" >&2
  done
  [ "$n" -eq 0 ] && { echo "No slides captured from $SLIDES" >&2; exit 4; }
else
  CHROME="${BROWSER_BIN:-}"
  if [ -z "$CHROME" ]; then
    for c in google-chrome chromium chromium-browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
      command -v "$c" >/dev/null 2>&1 && { CHROME="$c"; break; }
      [ -x "$c" ] && { CHROME="$c"; break; }
    done
  fi
  [ -z "$CHROME" ] && { echo "No agent-browser and no Chrome found. Set BROWSER_BIN." >&2; exit 3; }
  for f in "$SLIDES"/[0-9][0-9]-*.html; do
    name="$(basename "$f" .html)"
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
      --window-size=1920,1080 --screenshot="$FRAMES/$name.png" \
      --default-background-color=00000000 "$(to_url "$f")" >/dev/null 2>&1
    echo "captured $name"
  done
fi
echo "DONE -> $FRAMES"
