# narrated-demo

Turn a `scenes.json` into a narrated 1080p MP4 walkthrough — polished dark
slides + Deepgram Aura-2 voiceover, montaged with ffmpeg. Built for project
walkthroughs, architecture explainers, and take-home / submission videos.

This is a self-contained, portable [Claude Code skill](https://docs.claude.com)
— but the scripts are plain Python + bash and run fine on their own.

## Install (as a Claude Code skill)

Copy this folder into your skills directory:

```bash
cp -r narrated-demo ~/.claude/skills/        # user-level, all projects
# or:  cp -r narrated-demo .claude/skills/    # project-level
```

Claude will pick it up by its `SKILL.md` description (ask it to "make a demo
video"). Or just run the scripts directly.

## Use it directly

```bash
export DEEPGRAM_API_KEY=...          # required for voiceover
bash scripts/build.sh assets/example-scenes.json /tmp/demo /tmp/demo/out.mp4 "My Project"
```

Output: `/tmp/demo/out.mp4` (1920×1080, H.264/AAC).

## Iterate stage-by-stage

`build.sh` is just these four steps — run them individually to avoid re-spending
TTS while you tweak slides:

```bash
HERE=scripts
# 1. render slides -> HTML
python $HERE/make_slides.py scenes.json work/slides --footer "My Project" --assets .
# 2. rasterize -> 1920x1080 PNG  (agent-browser, or headless Chrome fallback)
bash $HERE/capture_slides.sh work/slides work/frames
# 3. narration -> NN.mp3  (idempotent; re-runs skip existing clips)
python $HERE/gen_tts_deepgram.py scenes.json work/audio
# 4. montage -> MP4
FF=ffmpeg bash $HERE/build_demo.sh work/frames work/audio out.mp4
```

Re-running after editing only slides? Use `SKIP_TTS=1 bash scripts/build.sh ...`
to reuse the audio you already generated.

## Slide kinds

See `SKILL.md` for the full table and `assets/example-scenes.json` for one of
every kind (title, diagram, code, bullets, table, and — not in the example but
supported — `image` to embed a screenshot). Mixing rendered slides with real
app screenshots in one video is the intended workflow: capture your app's
screens into the frames dir as `NN-name.png`, and author matching scenes.

## Platform notes

- **Windows:** ffmpeg via WSL works well. Run the build with WSL ffmpeg and
  `/mnt/c/...` paths, e.g.
  `FF=ffmpeg wsl -d Ubuntu -- bash /mnt/c/.../scripts/build_demo.sh ...`.
  Slide capture via `agent-browser` runs natively on Windows.
- **Voices:** set `DEMO_TTS_VOICE` (e.g. `aura-2-thalia-en` for a female voice).
- **No agent-browser?** `capture_slides.sh` falls back to headless Chrome /
  Chromium; set `BROWSER_BIN` to point at a specific binary.

## Credits

The TTS (`gen_tts_deepgram.py`) and montage (`build_demo.sh`) scripts are adapted
from the `demo-video` skill's proven still-clip-per-scene pipeline. The slide
renderer (`make_slides.py`) and orchestration are original to this skill.
