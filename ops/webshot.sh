#!/usr/bin/env bash
# Drive one Streamlit chat turn and screenshot it. Resolves the chat-input ref
# dynamically from a fresh snapshot each call (Streamlit reassigns @eN refs).
# Usage: webshot.sh "<message>" <wait_seconds> <out.png>
set -e
MSG="$1"; WAIT="${2:-12}"; OUT="$3"
REF=""
for i in $(seq 1 15); do
  REF=$(agent-browser snapshot -i 2>/dev/null | grep -i 'textbox' | grep -oE 'ref=e[0-9]+' | head -1 | cut -d= -f2)
  [ -n "$REF" ] && break
  sleep 1.5
done
if [ -z "$REF" ]; then echo "ERROR: chat input not found after retries"; exit 1; fi
agent-browser fill "@$REF" "$MSG" >/dev/null
agent-browser press Enter >/dev/null
echo "submitted via @$REF: $MSG ; waiting ${WAIT}s"
sleep "$WAIT"
agent-browser screenshot "$OUT" >/dev/null
echo "saved $OUT"
