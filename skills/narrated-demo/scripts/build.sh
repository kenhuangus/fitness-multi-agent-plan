#!/usr/bin/env bash
# One-shot orchestrator: scenes.json -> narrated MP4.
#   slides (HTML) -> frames (PNG) -> narration (MP3) -> montage (MP4)
#
# Usage:
#   DEEPGRAM_API_KEY=... bash build.sh <scenes.json> <workdir> <out.mp4> [footer]
#
# Env:
#   FF=/path/to/ffmpeg     ffmpeg binary (default: ffmpeg on PATH)
#   DEMO_TTS_VOICE=...      Deepgram Aura-2 voice (default: aura-2-arcas-en)
#   BROWSER_BIN=...         Chrome binary for slide capture fallback
#   SKIP_TTS=1             reuse existing <workdir>/audio (no Deepgram call)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENES="${1:?scenes.json}"; WORK="${2:?workdir}"; OUT="${3:?out.mp4}"; FOOTER="${4:-narrated-demo}"

mkdir -p "$WORK/slides" "$WORK/frames" "$WORK/audio"
ASSETS="$(cd "$(dirname "$SCENES")" && pwd)"

echo "==> 1/4 render slides"
python "$HERE/make_slides.py" "$SCENES" "$WORK/slides" --footer "$FOOTER" --assets "$ASSETS"

echo "==> 2/4 capture frames (1920x1080)"
bash "$HERE/capture_slides.sh" "$WORK/slides" "$WORK/frames"

echo "==> 3/4 narration (Deepgram Aura-2)"
if [ "${SKIP_TTS:-0}" = "1" ]; then echo "SKIP_TTS=1 — reusing $WORK/audio"; else
  python "$HERE/gen_tts_deepgram.py" "$SCENES" "$WORK/audio"
fi

echo "==> 4/4 montage"
FF="${FF:-ffmpeg}" bash "$HERE/build_demo.sh" "$WORK/frames" "$WORK/audio" "$OUT"
echo "DONE -> $OUT"
