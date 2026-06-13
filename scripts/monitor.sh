#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

require_arduino_cli

if [[ -z "${ARDUINO_PORT:-}" ]]; then
  echo "No serial port detected. Set ARDUINO_PORT or reconnect the board." >&2
  arduino-cli board list
  exit 1
fi

if [[ "${ARDUINO_CLI_MONITOR:-0}" == "1" ]]; then
  arduino-cli monitor \
    --port "$ARDUINO_PORT" \
    --fqbn "$ARDUINO_FQBN" \
    --config baudrate="${MONITOR_BAUD:-115200}",dtr=on,rts=off \
    --timestamp
else
  stty -f "$ARDUINO_PORT" "${MONITOR_BAUD:-115200}" cs8 -cstopb -parenb -ixon -ixoff -echo
  exec cat "$ARDUINO_PORT"
fi
