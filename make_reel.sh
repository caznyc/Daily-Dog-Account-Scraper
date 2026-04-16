#!/usr/bin/env bash
#
# make_reel.sh — produce a 9:16 Instagram Reel from a vertical source by:
#   1. Detecting the "sharp" central content band (rejects blurred/dark padding)
#      via per-row image-sharpness analysis.
#   2. Cropping out the blurred top/bottom bars.
#   3. Stacking a black top banner with white bold sans-serif text on top, plus
#      a small black bottom bar so the final is exactly 9:16.
#
# Usage: bash make_reel.sh [input.mp4] [output.mp4]

set -euo pipefail

FONT="$(dirname "$0")/fonts/PTSerif-Bold.ttf"
LINE1="You finally found a page dedicated to"
LINE2="Explaining Football"

INPUT="${1:-}"
OUTPUT="${2:-output.mp4}"

if [[ -z "$INPUT" ]]; then
  INPUT=$(find . -maxdepth 1 -type f -iname "*.mp4" ! -name "$(basename "$OUTPUT")" \
          -printf "%f\n" | head -n1)
  [[ -n "$INPUT" ]] || { echo "ERROR: no input .mp4 in $(pwd)" >&2; exit 1; }
fi
[[ -f "$INPUT" ]] || { echo "ERROR: input not found: $INPUT" >&2; exit 1; }
[[ -f "$FONT"  ]] || { echo "ERROR: font not found: $FONT"  >&2; exit 1; }

echo ">>> Input:  $INPUT"
echo ">>> Output: $OUTPUT"

SRC_W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width  -of csv=p=0 "$INPUT")
SRC_H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$INPUT")
DUR=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$INPUT")
echo ">>> Source: ${SRC_W}x${SRC_H}  duration=${DUR}s"

# --- Detect sharp content band ---
echo ">>> Analyzing sharpness..."
read -r CROP_Y CROP_H <<<"$(python3 - "$INPUT" "$DUR" <<'PY'
import subprocess, sys, numpy as np
from PIL import Image
import io

inp, dur = sys.argv[1], float(sys.argv[2])
# Sample ~12 frames evenly across the clip, skip first/last 2%
n = 12
ts = [dur * (0.02 + 0.96 * i/(n-1)) for i in range(n)]

rows = []
for t in ts:
    p = subprocess.run(
        ["ffmpeg","-hide_banner","-loglevel","error","-ss",f"{t:.2f}",
         "-i", inp, "-frames:v","1","-f","image2","-vcodec","png","-"],
        capture_output=True)
    if p.returncode != 0 or len(p.stdout) == 0:
        continue
    try:
        img = np.array(Image.open(io.BytesIO(p.stdout)).convert("L"), dtype=np.float32)
    except Exception:
        continue
    rows.append(np.abs(np.diff(img, axis=1)).std(axis=1))

if not rows:
    print("0 0")
    sys.exit(0)

A = np.median(np.stack(rows), axis=0)
H = len(A)

# Two complementary detectors, take the more aggressive (inner) crop on each
# side so we trim BOTH heavy blur padding and gradual blur fadeouts.
def first_above(arr, t):
    above = np.where(arr > t)[0]
    return int(above[0]) if above.size else 0

# (1) Edge-walk against an adaptive noise-floor threshold. Catches clips
#     with hard blur padding sitting near the sensor noise floor.
p15 = float(np.percentile(A, 15))
thr_floor = min(0.5, p15 * 1.6)
top_a = first_above(A, thr_floor)
bot_a = H - 1 - first_above(A[::-1], thr_floor)

# (2) Smoothed fraction-of-peak. Catches clips where the blur is a gradual
#     fadeout into a faint preview of another shot — the noise floor is
#     normal but the edges are still clearly less detailed than the centre.
smooth = np.convolve(A, np.ones(51)/51, mode='same')
peak = float(np.percentile(smooth, 95))
thr_peak = peak * 0.40
above = np.where(smooth > thr_peak)[0]
if above.size:
    top_b, bot_b = int(above[0]), int(above[-1])
else:
    top_b, bot_b = 0, H - 1

# Combine: more aggressive on each side (max of tops, min of bottoms).
top_raw = max(top_a, top_b)
bot_raw = min(bot_a, bot_b)

if bot_raw <= top_raw:
    print(f"0 {H}")
else:
    # Push TOP boundary inward only if there's >20 px of blur/dark before content
    if top_raw > 20:
        top = ((top_raw + 30) // 2) * 2
    else:
        top = 0
    # Expand BOTTOM boundary outward only if there's >20 px of blur/dark after
    if bot_raw < H - 20:
        bot = min(H - 1, ((bot_raw + 8) // 2) * 2)
    else:
        bot = ((H - 1) // 2) * 2
    h = ((bot - top + 1) // 2) * 2
    print(f"{top} {h}")
PY
)"
echo ">>> Sharp band: y=$CROP_Y  height=$CROP_H  (was ${SRC_H})"

if [[ -z "$CROP_H" || "$CROP_H" == "0" ]]; then
  echo "ERROR: could not detect sharp content band — skipping." >&2
  exit 1
fi

# --- Layout ---
W=$(( (SRC_W/2)*2 ))
FINAL_H=$(( (W * 16 / 9 / 2) * 2 ))
CONTENT_H=$CROP_H

# For sources that are already tightly cropped (no blur padding), the sharp
# band can occupy all or most of the frame — leaving no room for a banner.
# In that case, crop additional rows from the TOP of the sharp band so the
# video is "lowered" in the final composition (its visible content shifts
# down below the banner). Enforce a minimum banner height for consistent
# branding across clips, and a small bottom bar.
MIN_BANNER=500
MIN_BOTTOM=100
MAX_CONTENT=$(( FINAL_H - MIN_BANNER - MIN_BOTTOM ))

if (( CONTENT_H > MAX_CONTENT )); then
  EXTRA=$(( CONTENT_H - MAX_CONTENT ))
  CROP_Y=$(( ((CROP_Y + EXTRA) / 2) * 2 ))
  CONTENT_H=$MAX_CONTENT
  echo ">>> Content too tall for banner; cropped additional ${EXTRA} px from top (shifts video down)"
fi

REMAIN=$(( FINAL_H - CONTENT_H ))
# Distribute remaining space: ~65% to top banner, ~35% to bottom bar.
BANNER_H=$(( (REMAIN * 65 / 100 / 2) * 2 ))
(( BANNER_H < MIN_BANNER )) && BANNER_H=$MIN_BANNER
BOTTOM_H=$(( FINAL_H - CONTENT_H - BANNER_H ))

# Text styling (~5.2% of width font, left-aligned inset ~3.5% of width)
FS=$(python3 -c "print(int(round($W * 0.052)))")
PAD_X=$(python3 -c "print(int(round($W * 0.035)))")
# Position text block flush against the bottom of the banner (just above the
# video). drawtext y is the top of the glyph; a serif text block takes ~FS px
# per line + ~0.2*FS leading.
GAP=$(python3 -c "print(int(round($FS * 0.35)))")   # gap between text bottom and video
LINE2_Y=$(( BANNER_H - FS - GAP ))
LINE1_Y=$(python3 -c "print(int(round($LINE2_Y - $FS * 1.15)))")

echo ">>> Layout: ${W}x${FINAL_H}  banner=$BANNER_H  content=$CONTENT_H  bottom=$BOTTOM_H"
echo ">>> Text:   fs=$FS  pad_x=$PAD_X  y1=$LINE1_Y  y2=$LINE2_Y"

# --- Filter chain ---
FILTER="crop=${W}:${CONTENT_H}:0:${CROP_Y},\
pad=${W}:${FINAL_H}:0:${BANNER_H}:black,\
drawtext=fontfile=${FONT}:text='${LINE1}':fontcolor=white:fontsize=${FS}:x=${PAD_X}:y=${LINE1_Y},\
drawtext=fontfile=${FONT}:text='${LINE2}':fontcolor=white:fontsize=${FS}:x=${PAD_X}:y=${LINE2_Y}"

echo ">>> Encoding..."
ffmpeg -hide_banner -y -i "$INPUT" \
  -vf "$FILTER" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -profile:v high -level 4.0 -movflags +faststart \
  -c:a aac -b:a 128k -ar 44100 \
  -r 30 \
  "$OUTPUT"

echo ">>> Done: $OUTPUT"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,pix_fmt -of default=nw=1 "$OUTPUT"
