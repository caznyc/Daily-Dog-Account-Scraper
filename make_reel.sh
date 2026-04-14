#!/usr/bin/env bash
#
# make_reel.sh — crop letterbox bars from a vertical video and add a black
# top banner with white bold sans-serif text, exporting a 9:16 Instagram Reel.
#
# Usage:
#   bash make_reel.sh [input.mp4] [output.mp4]
#
# With no args, it picks the first *.mp4 in the current directory (excluding
# output.mp4) and writes output.mp4.

set -euo pipefail

FONT="/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
LINE1="You finally found a page dedicated to"
LINE2="Explaining Football"

INPUT="${1:-}"
OUTPUT="${2:-output.mp4}"

if [[ -z "$INPUT" ]]; then
  # Grab the first .mp4 in cwd that isn't the output file
  INPUT=$(find . -maxdepth 1 -type f -iname "*.mp4" ! -name "$(basename "$OUTPUT")" \
          -printf "%f\n" | head -n1)
  if [[ -z "$INPUT" ]]; then
    echo "ERROR: no input .mp4 found in $(pwd). Pass a path as the first arg." >&2
    exit 1
  fi
fi

if [[ ! -f "$INPUT" ]]; then
  echo "ERROR: input not found: $INPUT" >&2
  exit 1
fi

if [[ ! -f "$FONT" ]]; then
  echo "ERROR: font not found: $FONT" >&2
  exit 1
fi

echo ">>> Input:  $INPUT"
echo ">>> Output: $OUTPUT"

# --- Step 1: source dimensions ---
SRC_W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width  -of csv=p=0 "$INPUT")
SRC_H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$INPUT")
echo ">>> Source: ${SRC_W}x${SRC_H}"

# --- Step 2: cropdetect ---
echo ">>> Running cropdetect..."
CROP=$(ffmpeg -hide_banner -ss 1 -i "$INPUT" -t 10 -vf "cropdetect=24:2:0" -f null - 2>&1 \
       | grep -oE "crop=[0-9]+:[0-9]+:[0-9]+:[0-9]+" | tail -n1 | sed 's/^crop=//')

if [[ -z "$CROP" ]]; then
  echo "ERROR: cropdetect produced no result. Falling back to full frame." >&2
  CROP="${SRC_W}:${SRC_H}:0:0"
fi

W=$(echo "$CROP" | cut -d: -f1)
H=$(echo "$CROP" | cut -d: -f2)
X=$(echo "$CROP" | cut -d: -f3)
Y=$(echo "$CROP" | cut -d: -f4)
echo ">>> Cropdetect: W=$W H=$H X=$X Y=$Y"

# Force even dimensions for H.264
W=$(( (W/2)*2 ))
H=$(( (H/2)*2 ))

# --- Step 3: compute layout ---
FINAL_H=$(python3 -c "import math; print(((int(round($W * 16 / 9)))//2)*2)")
BANNER_H=$(( FINAL_H - H ))
if (( BANNER_H < 80 )); then
  # If the cropped content was already near full 9:16, force a readable banner.
  BANNER_H=$(( FINAL_H / 8 ))
  FINAL_H=$(( H + BANNER_H ))
  FINAL_H=$(( (FINAL_H/2)*2 ))
  BANNER_H=$(( FINAL_H - H ))
fi

FS=$(python3 -c "print(int(round($W * 0.042)))")
PAD_X=$(python3 -c "print(int(round($W * 0.035)))")
LINE1_Y=$(python3 -c "print(int(round($BANNER_H * 0.28)))")
LINE2_Y=$(python3 -c "print(int(round($BANNER_H * 0.28 + $FS * 1.2)))")

echo ">>> Layout: FINAL=${W}x${FINAL_H} banner_h=$BANNER_H fs=$FS pad_x=$PAD_X y1=$LINE1_Y y2=$LINE2_Y"

# --- Step 4: build filter chain ---
FILTER="crop=${W}:${H}:${X}:${Y},\
pad=${W}:${FINAL_H}:0:${BANNER_H}:black,\
drawtext=fontfile=${FONT}:text='${LINE1}':fontcolor=white:fontsize=${FS}:x=${PAD_X}:y=${LINE1_Y},\
drawtext=fontfile=${FONT}:text='${LINE2}':fontcolor=white:fontsize=${FS}:x=${PAD_X}:y=${LINE2_Y}"

# --- Step 5: encode ---
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
