#!/usr/bin/env python3
"""Generate Deepgram Aura-2 TTS narration, one mp3 per scene.

Usage:
    python gen_tts_deepgram.py <scenes.json> <out_dir> [--voice aura-2-arcas-en]

scenes.json: [ {"id": "01", "name": "intro", "narration": "..."}, ... ]
Writes <out_dir>/<id>.mp3 for each scene. Skips scenes whose mp3 already exists
(idempotent) unless --force. Reads DEEPGRAM_API_KEY from the environment; voice
defaults to $DEMO_TTS_VOICE or aura-2-arcas-en (a warm male voice).

Stdlib only (urllib) so it runs anywhere Python 3 is available.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_VOICE = os.getenv("DEMO_TTS_VOICE", "aura-2-arcas-en")
SPEAK_URL = "https://api.deepgram.com/v1/speak"


def synth(text: str, api_key: str, voice: str) -> bytes:
    # Deepgram speak: POST ?model=<voice> with {"text": ...} -> audio/mp3 bytes.
    url = f"{SPEAK_URL}?model={voice}&encoding=mp3"
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    scenes_path, out_dir = argv[1], argv[2]
    voice = DEFAULT_VOICE
    force = "--force" in argv
    if "--voice" in argv:
        voice = argv[argv.index("--voice") + 1]

    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        print("ERROR: DEEPGRAM_API_KEY not set in environment.", file=sys.stderr)
        return 1

    with open(scenes_path, encoding="utf-8") as f:
        scenes = json.load(f)

    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for sc in scenes:
        sid = str(sc["id"])
        text = sc["narration"].strip()
        out = os.path.join(out_dir, f"{sid}.mp3")
        if os.path.exists(out) and not force and os.path.getsize(out) > 0:
            print(f"{sid} skip (exists)")
            ok += 1
            continue
        if not text:
            print(f"{sid} SKIP (empty narration)", file=sys.stderr)
            continue
        try:
            audio = synth(text, api_key, voice)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            print(f"{sid} FAILED HTTP {e.code}: {detail}", file=sys.stderr)
            return 1
        with open(out, "wb") as fh:
            fh.write(audio)
        print(f"{sid} ok ({len(audio)} bytes, '{sc.get('name', '')}')")
        ok += 1

    print(f"DONE {ok}/{len(scenes)} clips -> {out_dir} (voice={voice})")
    return 0 if ok == len(scenes) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
