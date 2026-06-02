#!/usr/bin/env bash
# Montage a narrated walkthrough: pair each NN-*.png frame with its NN.mp3
# narration, make a still-image clip the length of the narration (+0.4s tail),
# then concat into one MP4 (H.264 / AAC, 30fps, yuv420p — broadly playable).
#
# Usage: [FF=/path/to/ffmpeg] build_demo.sh <frames_dir> <audio_dir> <out.mp4> [pad_dur]
#   frames_dir : contains NN-name.png  (NN = 01,02,...)
#   audio_dir  : contains NN.mp3
#   out.mp4    : output path
#   pad_dur    : trailing silence seconds per scene (default 0.4)
#
# FF defaults to `ffmpeg` on PATH; set FF to an ffmpeg-static binary otherwise.
# CANVAS=WxH (env, e.g. 1280x720) normalizes EVERY frame to that size with
#   scale-to-fit + black pad (letterbox/pillarbox), so portrait app screenshots
#   and landscape slides can be mixed in one video. Recommended whenever frames
#   differ in size — concat requires a single resolution.
set -euo pipefail

FRAMES="${1:?frames_dir}"; AUDIO="${2:?audio_dir}"; OUT="${3:?out.mp4}"; PAD="${4:-0.4}"
FF="${FF:-ffmpeg}"

WORK="$(dirname "$OUT")/.demo_build"
rm -rf "$WORK"; mkdir -p "$WORK"
LIST="$WORK/concat.txt"; : > "$LIST"

# Discover scene ids from the frame filenames (NN-*.png), sorted.
mapfile -t IDS < <(ls "$FRAMES"/[0-9][0-9]-*.png 2>/dev/null \
  | sed -E 's:.*/([0-9]{2})-.*:\1:' | sort -u)
if [[ ${#IDS[@]} -eq 0 ]]; then echo "No NN-*.png frames in $FRAMES" >&2; exit 2; fi

count=0
for i in "${IDS[@]}"; do
  img=$(ls "$FRAMES/${i}-"*.png 2>/dev/null | head -1 || true)
  aud="$AUDIO/${i}.mp3"
  [[ -z "${img:-}" ]] && { echo "MISSING FRAME $i" >&2; exit 2; }
  [[ ! -f "$aud" ]] && { echo "MISSING AUDIO $i" >&2; exit 2; }
  scene="$WORK/scene_${i}.mp4"
  if [[ -n "${CANVAS:-}" ]]; then
    cw="${CANVAS%x*}"; ch="${CANVAS#*x}"
    vf="scale=${cw}:${ch}:force_original_aspect_ratio=decrease,pad=${cw}:${ch}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
  else
    vf="scale=trunc(iw/2)*2:trunc(ih/2)*2"
  fi
  # Bound the clip EXPLICITLY by the audio duration (+PAD). Relying on -shortest
  # with a looped still image is unreliable across ffmpeg builds (the looped
  # video is infinite and the encode can run away to gigabytes) — so we compute
  # the duration and pass -t. apad keeps audio filling to the same length.
  # `ffmpeg -i` with no output exits non-zero; `|| true` keeps pipefail/errexit
  # from killing the script on the probe.
  dur=$({ "$FF" -hide_banner -i "$aud" 2>&1 || true; } | sed -nE 's/.*Duration: ([0-9:.]+),.*/\1/p' | head -1)
  secs=$(echo "$dur" | awk -F: '{print ($1*3600)+($2*60)+$3}')
  total=$(awk -v s="$secs" -v p="$PAD" 'BEGIN{printf "%.2f", s+p}')
  "$FF" -y -loglevel error -loop 1 -t "$total" -i "$img" -i "$aud" \
    -filter_complex "[1:a]apad[a];[0:v]${vf}[v]" \
    -map "[v]" -map "[a]" -t "$total" \
    -c:v libx264 -tune stillimage -r 30 -pix_fmt yuv420p \
    -c:a aac -b:a 192k "$scene"
  # concat resolves `file` paths relative to the LIST's own directory, and the
  # scenes live alongside it in WORK — so write the basename, not a path.
  echo "file 'scene_${i}.mp4'" >> "$LIST"
  count=$((count+1))
  echo "scene $i ok"
done

# Re-encode on concat (avoids timestamp seams between independently-made clips).
"$FF" -y -loglevel error -f concat -safe 0 -i "$LIST" \
  -c:v libx264 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k "$OUT"

echo "BUILT $count scenes -> $OUT"
"$FF" -hide_banner -i "$OUT" 2>&1 | grep -iE "Duration|Stream.*(Video|Audio)" || true
