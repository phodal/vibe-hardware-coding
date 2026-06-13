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

RELAY_ARGS=(
  --port "$ARDUINO_PORT"
  --baud "${MONITOR_BAUD:-115200}"
  --mode "${IOT_PANEL_RELAY_MODE:-mock}"
  --timeout "${IOT_PANEL_TIMEOUT:-15}"
)

if [[ -n "${IOT_PANEL_EVENTS_JSON:-}" ]]; then
  RELAY_ARGS+=(--events-json "$IOT_PANEL_EVENTS_JSON")
fi

if [[ -n "${IOT_PANEL_RELAY_ENDPOINT:-}" ]]; then
  RELAY_ARGS+=(--endpoint "$IOT_PANEL_RELAY_ENDPOINT")
fi

python3 "$ROOT_DIR/scripts/iot-panel-relay.py" "${RELAY_ARGS[@]}"

if [[ "${IOT_PANEL_VISUAL_SMOKE:-0}" == "1" ]]; then
  OCR_EXPECTED="${IOT_PANEL_OCR_EXPECTED:-OK}" "$ROOT_DIR/scripts/camera-ocr.sh"
fi
