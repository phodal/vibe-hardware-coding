#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

export SKETCH="${INTERACTION_DASHBOARD_SKETCH:-$ROOT_DIR/sketches/interaction_dashboard}"
export BUILD_PATH="${INTERACTION_DASHBOARD_BUILD_PATH:-$ROOT_DIR/.arduino-build/interaction_dashboard}"
export DISPLAY_ROTATION="${DISPLAY_ROTATION:-0}"
export ARDUINO_BUILD_PROPERTY="${ARDUINO_BUILD_PROPERTY:-compiler.cpp.extra_flags=-DDISPLAY_ROTATION=$DISPLAY_ROTATION}"

"$ROOT_DIR/scripts/upload.sh"
sleep "${INTERACTION_DASHBOARD_SETTLE_SECONDS:-1}"

if [[ -z "${ARDUINO_PORT_PINNED:-}" ]]; then
  ARDUINO_PORT="$(detect_arduino_port || printf '%s' "$ARDUINO_PORT")"
  export ARDUINO_PORT
fi

DASHBOARD_CHECK_ARGS=(
  --port "$ARDUINO_PORT"
  --baud "${MONITOR_BAUD:-115200}"
  --seconds "${INTERACTION_DASHBOARD_SECONDS:-5}"
  --pages "${INTERACTION_DASHBOARD_PAGES:-IMU,PWR,TOUCH,HOME}"
  --min-system-mv "${INTERACTION_DASHBOARD_MIN_SYSTEM_MV:-2500}"
  --min-acc-mag "${INTERACTION_DASHBOARD_MIN_ACC_MAG:-0.4}"
  --max-acc-mag "${INTERACTION_DASHBOARD_MAX_ACC_MAG:-1.8}"
)

if [[ "${INTERACTION_DASHBOARD_ALLOW_TOUCH_MISSING:-0}" == "1" ]]; then
  DASHBOARD_CHECK_ARGS+=(--allow-touch-missing)
fi

python3 "$ROOT_DIR/scripts/interaction-dashboard-check.py" "${DASHBOARD_CHECK_ARGS[@]}"

if [[ "${INTERACTION_DASHBOARD_VISUAL_SMOKE:-0}" == "1" ]]; then
  OCR_EXPECTED="${INTERACTION_DASHBOARD_OCR_EXPECTED:-OK}" "$ROOT_DIR/scripts/camera-ocr.sh"
fi
