#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
NES_CONTRA_LOG_DIR="${NES_CONTRA_LOG_DIR:-$LOG_DIR/nes-contra-$RUN_ID}"
mkdir -p "$NES_CONTRA_LOG_DIR"

export SKETCH="${NES_CONTRA_SKETCH:-$ROOT_DIR/sketches/nes_contra_emulator}"
export BUILD_PATH="${NES_CONTRA_BUILD_PATH:-$ROOT_DIR/.arduino-build/nes_contra_emulator}"
export DISPLAY_ROTATION="${DISPLAY_ROTATION:-0}"
export DISPLAY_BRIGHTNESS="${DISPLAY_BRIGHTNESS:-96}"
export ARDUINO_BUILD_PROPERTY="${ARDUINO_BUILD_PROPERTY:-compiler.cpp.extra_flags=-DDISPLAY_ROTATION=$DISPLAY_ROTATION -DDISPLAY_BRIGHTNESS=$DISPLAY_BRIGHTNESS}"

NES_CONTRA_UPLOAD_SPEED="${NES_CONTRA_UPLOAD_SPEED:-460800}"
if [[ -n "$NES_CONTRA_UPLOAD_SPEED" ]]; then
  if [[ "$ARDUINO_FQBN" == *UploadSpeed=* ]]; then
    ARDUINO_FQBN="$(printf '%s' "$ARDUINO_FQBN" | sed -E "s/UploadSpeed=[0-9]+/UploadSpeed=$NES_CONTRA_UPLOAD_SPEED/")"
  else
    ARDUINO_FQBN="$ARDUINO_FQBN,UploadSpeed=$NES_CONTRA_UPLOAD_SPEED"
  fi
  export ARDUINO_FQBN
fi

"$ROOT_DIR/scripts/upload.sh"
sleep "${NES_CONTRA_SETTLE_SECONDS:-1}"

if [[ -z "${ARDUINO_PORT_PINNED:-}" ]]; then
  ARDUINO_PORT="$(detect_arduino_port || printf '%s' "$ARDUINO_PORT")"
  export ARDUINO_PORT
fi

NES_CONTRA_CHECK_ARGS=(
  --port "$ARDUINO_PORT"
  --baud "${MONITOR_BAUD:-115200}"
  --seconds "${NES_CONTRA_SECONDS:-4}"
)

if [[ "${NES_CONTRA_ALLOW_TOUCH_MISSING:-0}" == "1" ]]; then
  NES_CONTRA_CHECK_ARGS+=(--allow-touch-missing)
fi

python3 "$ROOT_DIR/scripts/nes-contra-check.py" "${NES_CONTRA_CHECK_ARGS[@]}" | tee "$NES_CONTRA_LOG_DIR/serial-check.log"
echo "nes_contra_smoke_log path=$NES_CONTRA_LOG_DIR/serial-check.log"

if [[ "${NES_CONTRA_VISUAL_SMOKE:-0}" == "1" ]]; then
  OCR_EXPECTED="${NES_CONTRA_OCR_EXPECTED:-OK}" \
    OCR_PREPROCESS_MODE="${OCR_PREPROCESS_MODE:-color}" \
    OCR_SCALE_WIDTH="${OCR_SCALE_WIDTH:-2400}" \
    "$ROOT_DIR/scripts/camera-ocr.sh"
fi
