---
name: narrated-demo
description: >-
  Turn a JSON list of scenes into a narrated 1080p MP4 walkthrough. Renders
  polished dark slides (title, bullets, code with syntax highlighting,
  requirement/feature tables, architecture diagrams, and embedded screenshots),
  generates voiceover with Deepgram Aura-2 TTS, and montages everything with
  ffmpeg — one still per scene held for the length of its narration. Use when a
  user asks to "make a demo video", "record a walkthrough", "produce a
  submission/architecture video", "narrate these screenshots/slides", or turn a
  project into a short explainer with voiceover.
---

# narrated-demo

Author a `scenes.json`, run one command, get a narrated MP4. Each scene is one
still frame (a rendered slide or a screenshot) shown for exactly as long as its
spoken narration. Built for project walkthroughs, architecture explainers, and
take-home / submission videos.

## Requirements

- **Python 3** (stdlib only — no pip install needed for the scripts).
- **ffmpeg** on `PATH` (or set `FF=/path/to/ffmpeg`). On Windows, WSL's ffmpeg
  works: `FF=ffmpeg wsl -d Ubuntu -- bash build.sh ...` with `/mnt/c/...` paths.
- **A headless browser** to rasterize slides — `agent-browser` if installed,
  otherwise headless Chrome/Chromium (auto-detected; override with `BROWSER_BIN`).
- **`DEEPGRAM_API_KEY`** in the environment for narration.

## Quick start

```bash
export DEEPGRAM_API_KEY=...                 # required for voiceover
bash scripts/build.sh assets/example-scenes.json /tmp/demo /tmp/demo/out.mp4 "My Project"
# -> /tmp/demo/out.mp4   (1920x1080, H.264/AAC)
```

`build.sh` runs the four stages in order; you can also run them individually
(see README.md) to iterate on slides without re-spending TTS.

## The scenes.json model

An array of scene objects. `id` (zero-padded ordinal) sets play order; every
scene needs a `narration` string. Pick a `kind` per scene:

| kind | fields | use for |
|------|--------|---------|
| `title` | `title`, `subtitle?`, `kicker?` | opening / section title |
| `bullets` | `title`, `bullets[]`, `kicker?` | features, takeaways |
| `code` | `title`, `subtitle?`, `code` | show implementation (comments auto-dimmed) |
| `table` | `title`, `rows[[left, right_html]]` | requirement→file maps, comparisons |
| `diagram` | `title`, `nodes[]`, `note?` | architecture / flow (vertical) |
| `image` | `title`, `image`, `caption?` | embed a screenshot, fit-to-frame |

`image` paths resolve relative to the scenes.json directory. `table` right-cells
and accept inline HTML (e.g. `<code>hub.py</code>`). For `diagram`, each `nodes`
entry is either `{label, sub?, accent?}` or `{row:[{label,sub?}, ...]}` for a row
of leaf boxes. See `assets/example-scenes.json` for one of every kind.

## Pipeline (what build.sh does)

1. `make_slides.py scenes.json work/slides` → one `NN-name.html` per scene.
2. `capture_slides.sh work/slides work/frames` → screenshot each to `NN-name.png`
   at 1920×1080.
3. `gen_tts_deepgram.py scenes.json work/audio` → `NN.mp3` per scene (Aura-2;
   idempotent — re-runs skip existing clips).
4. `build_demo.sh work/frames work/audio out.mp4` → still-clip per scene
   (+0.4 s tail), concatenated to one MP4.

## Narration tips (for Aura-2)

- One breath-paragraph per scene, 1–3 sentences, present tense.
- Spell tricky tokens phonetically: "L L M", "A P I", "Jason" (JSON), "rapid fuzz".
- Name what's on screen, then why it matters.

## Files

- `scripts/make_slides.py` — scenes.json → styled HTML slides (the renderer).
- `scripts/capture_slides.sh` — HTML → 1920×1080 PNG (agent-browser or Chrome).
- `scripts/gen_tts_deepgram.py` — scenes.json → `NN.mp3` via Deepgram Aura-2.
- `scripts/build_demo.sh` — frames + audio → narrated MP4 (ffmpeg).
- `scripts/build.sh` — runs all four end-to-end.
- `assets/example-scenes.json` — a complete demo using every slide kind.
