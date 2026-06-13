#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

export SKETCH="${SENSOR_STATUS_SKETCH:-$ROOT_DIR/sketches/sensor_status_probe}"
export BUILD_PATH="${SENSOR_STATUS_BUILD_PATH:-$ROOT_DIR/.arduino-build/sensor_status_probe}"
export DISPLAY_ROTATION="${DISPLAY_ROTATION:-0}"
export ARDUINO_BUILD_PROPERTY="${ARDUINO_BUILD_PROPERTY:-compiler.cpp.extra_flags=-DDISPLAY_ROTATION=$DISPLAY_ROTATION}"

"$ROOT_DIR/scripts/upload.sh"
sleep "${SENSOR_STATUS_SETTLE_SECONDS:-1}"

if [[ -z "${ARDUINO_PORT_PINNED:-}" ]]; then
  ARDUINO_PORT="$(detect_arduino_port || printf '%s' "$ARDUINO_PORT")"
  export ARDUINO_PORT
fi

python3 "$ROOT_DIR/scripts/sensor-status-check.py" \
  --port "$ARDUINO_PORT" \
  --baud "${MONITOR_BAUD:-115200}" \
  --seconds "${SENSOR_STATUS_SECONDS:-8}" \
  --min-system-mv "${SENSOR_MIN_SYSTEM_MV:-2500}" \
  --min-vbus-mv "${SENSOR_MIN_VBUS_MV:-0}" \
  --min-acc-mag "${SENSOR_MIN_ACC_MAG:-0.4}" \
  --max-acc-mag "${SENSOR_MAX_ACC_MAG:-1.8}"

if [[ "${SENSOR_STATUS_VISUAL_SMOKE:-0}" == "1" ]]; then
  OCR_EXPECTED="${SENSOR_STATUS_OCR_EXPECTED:-OK}" "$ROOT_DIR/scripts/camera-ocr.sh"
fi
