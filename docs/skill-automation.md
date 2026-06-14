# Skill Automation

This repo keeps the agent-facing Waveshare Skill in `skills/waveshare-esp32s3-amoled/` and mirrors the same instructions into the global Codex Skill directory.

`make claude-skill-smoke` validates that an external Claude Code agent can read the repo Skill and invoke the Skill helper for the non-audio visual smoke path.

## Modes

```bash
make claude-skill-smoke
CLAUDE_SKILL_SMOKE_MODE=audit make claude-skill-smoke
```

- `visual`: default mode. Claude runs the repo Skill helper, uploads `sketches/display_ocr_check`, captures a camera frame, OCRs `OK`, and checks red/green/blue/yellow swatch geometry.
- `audit`: no-upload fallback. Claude runs the repo Skill helper for `feature-matrix check`.

The wrapper writes two artifacts under `.logs/`:

- `claude-skill-smoke-<timestamp>.txt`: Claude's own transcript.
- `claude-skill-smoke-command-<timestamp>.txt`: the exact command output that the wrapper checks for pass markers.

The prompt forbids edits, XiaoZhi flash/restore, and audio paths. The wrapper also reports `audio=0` in its summary line.

## Verified Locally

- `CLAUDE_SKILL_SMOKE_MODE=audit make claude-skill-smoke`: passed through the local Claude CLI and recorded `feature_matrix_summary features=12 verified=10 partial=0 external_or_quiet=2 issues=0` in `.logs/claude-skill-smoke-command-20260614-083850.txt`.
- `make claude-skill-smoke`: passed through the local Claude CLI, uploaded the visual calibration sketch to `/dev/cu.usbmodem83101`, captured `/Users/phodal/hardware/arduino/.logs/camera-ocr-20260614-084104.jpg`, saw `OCR validation passed.`, and recorded `color_swatch_summary status=passed` in `.logs/claude-skill-smoke-command-20260614-083916.txt`.
