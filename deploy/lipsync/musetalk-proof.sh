#!/usr/bin/env bash
# MuseTalk 30 second proof. Runs on a rented GPU pod, never on the VPS.
#
# UNVERIFIED as of 2026-09-15: written from the MuseTalk README's own commands
# (install, download_weights.sh, inference.sh v1.5 normal) and not yet executed,
# because this repository's session container has no GPU. The first run is the
# proof itself. If a step fails, the README at
# https://github.com/TMElyralab/MuseTalk is the source of truth, not this file.
#
# Before running, put two files next to this script:
#   in/tee.mp4   the first 30 seconds of recording take A (landscape, talking)
#   in/line.wav  30 seconds of the cloned narration, 16 kHz mono
#
# Usage:  bash musetalk-proof.sh [bbox_shift]      default bbox_shift is 0
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BBOX_SHIFT="${1:-0}"
WORK="${MUSETALK_WORK:-$HERE/work}"
IN_VIDEO="$HERE/in/tee.mp4"
IN_AUDIO="$HERE/in/line.wav"
OUT_DIR="$HERE/out"

for f in "$IN_VIDEO" "$IN_AUDIO"; do
  if [ ! -s "$f" ]; then
    echo "missing input: $f" >&2
    exit 2
  fi
done

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "no nvidia-smi on this machine; MuseTalk needs a CUDA GPU. Run this on the rented pod." >&2
  exit 3
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

mkdir -p "$WORK" "$OUT_DIR"
cd "$WORK"

if [ ! -d MuseTalk ]; then
  git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git
fi
cd MuseTalk

# Dependencies exactly as the README lists them (read 2026-09-15). The torch
# pin is the README's; a pod template that already carries a newer torch may
# work too, but the pinned set is the one the authors tested.
python3 -m pip install --quiet torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
python3 -m pip install --quiet -r requirements.txt
python3 -m pip install --quiet --no-cache-dir -U openmim
mim install --quiet mmengine
mim install --quiet "mmcv==2.0.1"
mim install --quiet "mmdet==3.1.0"
mim install --quiet "mmpose==1.1.0"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is not on PATH; install it (apt-get install -y ffmpeg) and rerun" >&2
  exit 4
fi
export FFMPEG_PATH="$(dirname "$(command -v ffmpeg)")"

# Weights through the project's own script, into ./models as the README lays out.
if [ ! -s models/musetalkV15/unet.pth ]; then
  sh ./download_weights.sh
fi

# One inference config for the proof. The README's keys are video_path,
# audio_path and bbox_shift; the task name is ours.
mkdir -p configs/inference
cat > configs/inference/proof.yaml <<YAML
proof:
  video_path: "$IN_VIDEO"
  audio_path: "$IN_AUDIO"
  bbox_shift: $BBOX_SHIFT
YAML

# inference.sh v1.5 normal is the README's documented entry point. It reads the
# config it is given through the script's own arguments; if the checked out
# version wants the config passed differently, run the python entry it wraps
# and pass --inference_config configs/inference/proof.yaml.
sh inference.sh v1.5 normal --inference_config configs/inference/proof.yaml --result_dir "$OUT_DIR" || {
  echo "inference.sh refused those arguments; falling back to the python entry" >&2
  python3 -m scripts.inference --inference_config configs/inference/proof.yaml --result_dir "$OUT_DIR" --unet_model_path models/musetalkV15/unet.pth --unet_config models/musetalkV15/musetalk.json --version v15
}

echo
echo "results under $OUT_DIR:"
ls -la "$OUT_DIR"
echo
echo "Watch the file before deciding anything. bbox_shift used: $BBOX_SHIFT"
