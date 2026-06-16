#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/arduino-env.sh"

CAMERA_RESET_RESTART_SERVICES="${CAMERA_RESET_RESTART_SERVICES:-1}"
CAMERA_RESET_QUIT_APPS="${CAMERA_RESET_QUIT_APPS:-0}"
CAMERA_RESET_QUIT_CHAT_APPS="${CAMERA_RESET_QUIT_CHAT_APPS:-0}"
CAMERA_RESET_CHECK="${CAMERA_RESET_CHECK:-1}"
CAMERA_RESET_REQUIRE_READY="${CAMERA_RESET_REQUIRE_READY:-1}"
CAMERA_CAPTURE_TIMEOUT="${CAMERA_CAPTURE_TIMEOUT:-8}"

quit_app() {
  local app="$1"
  osascript -e "tell application \"$app\" to quit" >/dev/null 2>&1 || true
}

if [[ "$CAMERA_RESET_QUIT_APPS" == "1" ]]; then
  quit_app "FaceTime"
  quit_app "Photo Booth"
  quit_app "QuickTime Player"
  quit_app "zoom.us"
  quit_app "Microsoft Teams"
elif [[ "$CAMERA_RESET_QUIT_APPS" != "0" ]]; then
  echo "CAMERA_RESET_QUIT_APPS must be 0 or 1." >&2
  exit 2
fi

if [[ "$CAMERA_RESET_QUIT_CHAT_APPS" == "1" ]]; then
  quit_app "WeChat"
  quit_app "WeCom"
  quit_app "企业微信"
elif [[ "$CAMERA_RESET_QUIT_CHAT_APPS" != "0" ]]; then
  echo "CAMERA_RESET_QUIT_CHAT_APPS must be 0 or 1." >&2
  exit 2
fi

if [[ "$CAMERA_RESET_RESTART_SERVICES" == "1" ]]; then
  killall VDCAssistant ContinuityCaptureAgent >/dev/null 2>&1 || true
elif [[ "$CAMERA_RESET_RESTART_SERVICES" != "0" ]]; then
  echo "CAMERA_RESET_RESTART_SERVICES must be 0 or 1." >&2
  exit 2
fi

sleep "${CAMERA_RESET_SETTLE_SECONDS:-2}"

ready_status=skipped
latest_summary=none
recommendation=not_checked

if [[ "$CAMERA_RESET_CHECK" == "1" ]]; then
  set +e
  CAMERA_CAPTURE_TIMEOUT="$CAMERA_CAPTURE_TIMEOUT" \
    CAMERA_DIAGNOSE_FFMPEG=0 \
    CAMERA_DIAGNOSE_EXTRA_PROBES=0 \
    CAMERA_DIAGNOSE_REQUIRE_CAPTURE=1 \
    "$ROOT_DIR/scripts/camera-diagnose.sh"
  ready_status=$?
  set -e

  latest_summary="$(ls -t "$LOG_DIR"/camera-diagnose-*/summary.txt 2>/dev/null | head -1 || true)"
  if [[ -z "$latest_summary" ]]; then
    latest_summary=none
  elif [[ -f "$latest_summary" ]]; then
    recommendation="$(sed -n 's/^capture_recommendation=//p' "$latest_summary" | tail -1)"
    if [[ -z "$recommendation" ]]; then
      recommendation=unknown
    fi
  fi
elif [[ "$CAMERA_RESET_CHECK" != "0" ]]; then
  echo "CAMERA_RESET_CHECK must be 0 or 1." >&2
  exit 2
fi

echo "camera_reset_summary services_restarted=$CAMERA_RESET_RESTART_SERVICES quit_apps=$CAMERA_RESET_QUIT_APPS quit_chat_apps=$CAMERA_RESET_QUIT_CHAT_APPS ready_status=$ready_status recommendation=$recommendation summary=$latest_summary"

if [[ "$CAMERA_RESET_REQUIRE_READY" == "1" && "$ready_status" != "0" ]]; then
  exit "$ready_status"
elif [[ "$CAMERA_RESET_REQUIRE_READY" != "0" && "$CAMERA_RESET_REQUIRE_READY" != "1" ]]; then
  echo "CAMERA_RESET_REQUIRE_READY must be 0 or 1." >&2
  exit 2
fi
