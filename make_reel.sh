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
        capture_output=True, check=True)
    img = np.array(Image.open(io.BytesIO(p.stdout)).convert("L"), dtype=np.float32)
    rows.append(np.abs(np.diff(img, axis=1)).std(axis=1))

A = np.median(np.stack(rows), axis=0)
H = len(A)
# Threshold 1.5 catches the full sharp band including caption tails that sit
# right at the lower edge. Asymmetric insets: push the TOP boundary inward by
# 30 px to clear the gradual blur transition, but expand the BOTTOM by 8 px
# so in-video captions don't get clipped.
thr = 1.5
sharp = np.where(A > thr)[0]
if sharp.size == 0:
    print(f"0 {H}")
else:
    top = int(sharp[0])
    bot = int(sharp[-1])
    top = max(0, ((top + 30)//2)*2)
    bot = min(H-1, ((bot + 8)//2)*2)
    h = ((bot - top + 1)//2)*2
    print(f"{top} {h}")
PY
)"
echo ">>> Sharp band: y=$CROP_Y  height=$CROP_H  (was ${SRC_H})"

# --- Layout ---
W=$(( (SRC_W/2)*2 ))
FINAL_H=$(( (W * 16 / 9 / 2) * 2 ))
CONTENT_H=$CROP_H

# Make sure the cropped content fits inside 9:16
if (( CONTENT_H >= FINAL_H )); then
  echo "ERROR: cropped content (${CONTENT_H}) >= 9:16 frame (${FINAL_H}); cannot fit." >&2
  exit 1
fi

REMAIN=$(( FINAL_H - CONTENT_H ))
# Distribute remaining space: ~60% to top banner, ~40% to bottom bar.
BANNER_H=$(( (REMAIN * 60 / 100 / 2) * 2 ))
BOTTOM_H=$(( FINAL_H - CONTENT_H - BANNER_H ))

# Text styling (~5% of width font, ~3.5% left inset)
FS=$(python3 -c "print(int(round($W * 0.048)))")
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
