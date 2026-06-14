#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="${CLAUDE_SKILL_DIR:-$ROOT_DIR/skills/waveshare-esp32s3-amoled}"
SKILL_HELPER="$SKILL_DIR/scripts/waveshare-arduino-cli.sh"
LOG_DIR="${CLAUDE_SKILL_LOG_DIR:-$ROOT_DIR/.logs}"
STAMP="$(date +%Y%m%d-%H%M%S)"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
CLAUDE_MODEL="${CLAUDE_MODEL:-}"
CLAUDE_MAX_BUDGET_USD="${CLAUDE_MAX_BUDGET_USD:-1.50}"
CLAUDE_PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-bypassPermissions}"
CLAUDE_TRANSCRIPT="$LOG_DIR/claude-skill-smoke-$STAMP.txt"
COMMAND_LOG="$LOG_DIR/claude-skill-smoke-command-$STAMP.txt"

mkdir -p "$LOG_DIR"

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "Claude CLI not found: $CLAUDE_BIN" >&2
  exit 2
fi

if [[ ! -x "$SKILL_HELPER" ]]; then
  echo "Skill helper is missing or not executable: $SKILL_HELPER" >&2
  exit 2
fi

MODE="${CLAUDE_SKILL_SMOKE_MODE:-visual}"
case "$MODE" in
  visual)
    SMOKE_COMMAND="DISPLAY_ROTATION=2 DISPLAY_BRIGHTNESS=96 CAMERA_DEVICE=0 CAMERA_SIZE=1280x720 CAMERA_CAPTURE_ENGINE=swift CAMERA_EXPOSURE_POINT=0.5,0.65 CAMERA_FOCUS_POINT=0.5,0.65 CAMERA_WARMUP_FRAMES=30 OCR_PREPROCESS_MODE=color OCR_EQ_BRIGHTNESS=-0.05 OCR_EQ_CONTRAST=1.3 OCR_GAMMA=0.9 COLOR_SWATCH_CHECK=1 '$SKILL_HELPER' visual-smoke '$ROOT_DIR'"
    REQUIRED_MARKERS=("OCR validation passed." "color_swatch_summary status=passed")
    ;;
  audit)
    SMOKE_COMMAND="'$SKILL_HELPER' feature-matrix '$ROOT_DIR' check"
    REQUIRED_MARKERS=("feature_matrix_summary")
    ;;
  *)
    echo "CLAUDE_SKILL_SMOKE_MODE must be one of: visual, audit" >&2
    exit 2
    ;;
esac

read -r -d '' PROMPT <<PROMPT || true
You are validating the Codex Skill at:
$SKILL_DIR/SKILL.md

Constraints:
- Do not edit files.
- Do not run audio playback, microphone capture, speaker tests, audio-vad-smoke, speaker-output-smoke, or "say".
- Do not run XiaoZhi flash or restore.
- Run exactly this Bash command once from $ROOT_DIR:

mkdir -p '$LOG_DIR' && cd '$ROOT_DIR' && ( set -euo pipefail; $SMOKE_COMMAND ) 2>&1 | tee '$COMMAND_LOG'

After the command finishes, print one final line:
claude_skill_smoke_complete mode=$MODE command_log=$COMMAND_LOG
PROMPT

CLAUDE_ARGS=(-p "$PROMPT" --max-budget-usd "$CLAUDE_MAX_BUDGET_USD" --allowedTools Bash,Read --disallowedTools Edit,Write,MultiEdit,NotebookEdit --permission-mode "$CLAUDE_PERMISSION_MODE")
if [[ -n "$CLAUDE_MODEL" ]]; then
  CLAUDE_ARGS+=(--model "$CLAUDE_MODEL")
fi

"$CLAUDE_BIN" "${CLAUDE_ARGS[@]}" | tee "$CLAUDE_TRANSCRIPT"

if [[ ! -s "$COMMAND_LOG" ]]; then
  echo "claude_skill_smoke_summary status=failed reason=missing_command_log transcript=$CLAUDE_TRANSCRIPT audio=0" >&2
  exit 1
fi

for marker in "${REQUIRED_MARKERS[@]}"; do
  if ! grep -Fq "$marker" "$COMMAND_LOG"; then
    echo "claude_skill_smoke_summary status=failed reason=missing_marker marker=$marker command_log=$COMMAND_LOG transcript=$CLAUDE_TRANSCRIPT audio=0" >&2
    exit 1
  fi
done

printf 'claude_skill_smoke_summary status=passed mode=%s command_log=%s transcript=%s audio=0\n' \
  "$MODE" "$COMMAND_LOG" "$CLAUDE_TRANSCRIPT"
