#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

export SKETCH="${IOT_PANEL_SKETCH:-$ROOT_DIR/sketches/iot_control_panel}"
export BUILD_PATH="${IOT_PANEL_BUILD_PATH:-$ROOT_DIR/.arduino-build/iot_control_panel}"
export DISPLAY_ROTATION="${DISPLAY_ROTATION:-0}"
export ARDUINO_BUILD_PROPERTY="${ARDUINO_BUILD_PROPERTY:-compiler.cpp.extra_flags=-DDISPLAY_ROTATION=$DISPLAY_ROTATION}"

"$ROOT_DIR/scripts/upload.sh"
sleep "${IOT_PANEL_SETTLE_SECONDS:-1}"

if [[ -z "${ARDUINO_PORT_PINNED:-}" ]]; then
  ARDUINO_PORT="$(detect_arduino_port || printf '%s' "$ARDUINO_PORT")"
  export ARDUINO_PORT
fi

IOT_PANEL_CHECK_ARGS=(
  --port "$ARDUINO_PORT"
  --baud "${MONITOR_BAUD:-115200}"
  --seconds "${IOT_PANEL_SECONDS:-4}"
)

if [[ "${IOT_PANEL_ALLOW_TOUCH_MISSING:-0}" == "1" ]]; then
  IOT_PANEL_CHECK_ARGS+=(--allow-touch-missing)
fi

python3 "$ROOT_DIR/scripts/iot-panel-check.py" "${IOT_PANEL_CHECK_ARGS[@]}"

if [[ "${IOT_PANEL_VISUAL_SMOKE:-0}" == "1" ]]; then
  OCR_EXPECTED="${IOT_PANEL_OCR_EXPECTED:-OK}" "$ROOT_DIR/scripts/camera-ocr.sh"
fi
