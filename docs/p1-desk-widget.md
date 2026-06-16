# P1 Desk Widget

The `desk_widget` sketch is a serial-driven desktop AI widget surface for the Waveshare ESP32-S3-Touch-AMOLED-1.75C. It focuses on always-on display workflows that do not require audio: status lights, GitHub/CI alerts, calendar reminders, a pomodoro timer, and short AI summaries.

## What It Proves

- The AMOLED can render a compact desk widget with multiple pages.
- The CST9217 touch controller initializes and can cycle pages when tapped.
- A host-side relay can push CI, GitHub, alert, calendar, timer, and AI-summary state over serial.
- Automation can validate the widget without network credentials or audio devices.

## Commands

```bash
make desk-widget-build
make desk-widget-smoke
make desk-widget-relay-smoke
DESK_WIDGET_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make desk-widget-smoke
```

The smoke script uploads the sketch, waits for `WIDGET_READY`, sends CI/GitHub/alert/calendar/timer/summary commands, and verifies `WIDGET_STATE` plus the serial page flow.

`make desk-widget-relay-smoke` uploads the same sketch and runs `scripts/desk-widget-relay.py`. The relay turns mock, JSON-file, or HTTP event payloads into the board serial protocol. This is the host-side adapter gate before using real GitHub, CI, calendar, or LLM credentials.

Relay payload shape:

```json
{
  "ci": {"state": "FAIL", "label": "build red"},
  "github": {"count": 7},
  "calendar": {"count": 2, "next": "standup in 15"},
  "alerts": ["review needed"],
  "timer": {"minutes": 25, "start": true},
  "summary": "AI summary ready for standup"
}
```

## Serial Protocol

- `PING` returns `PONG`.
- `PAGE:HOME`, `PAGE:STATUS`, `PAGE:TIMER`, `PAGE:CALENDAR`, and `PAGE:SUMMARY` switch pages.
- `WIDGET:CI:<OK|WARN|FAIL>[:label]` sets the CI status card.
- `WIDGET:GITHUB:<count>` sets the GitHub/notification count.
- `WIDGET:ALERT:<text>` increments the alert count and updates alert text.
- `WIDGET:CALENDAR:<count>[:next]` updates the calendar reminder page.
- `TIMER:SET:<minutes>`, `TIMER:START`, `TIMER:PAUSE`, and `TIMER:RESET` control the pomodoro card.
- `WIDGET:SUMMARY:<text>` updates the AI summary card.
- `STATE?` emits `WIDGET_STATE`.

## Notes

This is a control-plane and UI slice. It does not require Wi-Fi credentials yet; a future host relay can translate GitHub, calendar, CI, or LLM events into the same serial protocol before moving the device to direct Wi-Fi integrations.

## Verified Locally

- `make desk-widget-build`: passed.
- `make desk-widget-smoke`: uploaded to `/dev/cu.usbmodem83101` and validated direct serial commands for CI/GitHub/alert/calendar/timer/summary.
- `SKIP_BUILD=1 make desk-widget-relay-smoke`: uploaded to `/dev/cu.usbmodem83101` and validated mock event relay for CI/GitHub/alert/calendar/timer/summary.
- `SKIP_BUILD=1 skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh desk-widget /Users/phodal/hardware/arduino relay`: passed through the repo Skill helper.
- `SKIP_BUILD=1 /Users/phodal/.codex/skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh desk-widget /Users/phodal/hardware/arduino relay`: passed through the global Skill helper.
- `make hardware-smoke-suite HARDWARE_SMOKE_ARGS="--targets cloud-ai-terminal,imu-interaction,desk-widget --per-target-timeout 420 --max-failures 1"`: built, uploaded, and passed `desk-widget-relay-smoke` on `/dev/cu.usbmodem83101`.
- Latest suite summary: `.logs/hardware-smoke-suite/20260614-045308/summary.json`.
- Latest target log: `.logs/hardware-smoke-suite/20260614-045308/desk-widget.log`.
- Observed build size: `435187 bytes` program storage and `23240 bytes` dynamic memory.
- Observed relay result: `{"status": "ok", "mode": "mock", "ci": {"state": "FAIL", "label": "build red"}, "github": {"count": 7}, "alert_count": 1}`.
- `SKIP_BUILD=1 make desk-widget-smoke`: uploaded to `/dev/cu.usbmodem83101` and passed direct serial flow including `WIDGET:CALENDAR:2:standup in 15`, `page=CALENDAR`, and `calendar=2`.
- `SKIP_BUILD=1 make desk-widget-relay-smoke`: uploaded to `/dev/cu.usbmodem83101` and passed mock relay flow with calendar payload `{"count": 2, "next": "standup in 15"}`.
- `make hardware-smoke-suite HARDWARE_SMOKE_ARGS="--target desk-widget --skip-build --per-target-timeout 240 --max-failures 1"`: uploaded and passed the standard suite target with CI/GitHub/alert/calendar/timer/summary relay coverage.
- Latest calendar suite summary: `.logs/hardware-smoke-suite/20260614-052802/summary.json`.
- Latest calendar suite target log: `.logs/hardware-smoke-suite/20260614-052802/desk-widget.log`.
- Latest build size: `435871 bytes` program storage and `23312 bytes` dynamic memory.
- Observed calendar relay result: `{"status": "ok", "mode": "mock", "ci": {"state": "FAIL", "label": "build red"}, "github": {"count": 7}, "calendar": {"count": 2, "next": "standup in 15"}, "alert_count": 1}`.
- `SKIP_BUILD=1 DESK_WIDGET_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 DESK_WIDGET_SECONDS=4 CAMERA_CAPTURE_TIMEOUT=8 make desk-widget-smoke`: uploaded to `/dev/cu.usbmodem83101`, validated the serial CI/GitHub/alert/calendar/timer/summary flow, returned to `PAGE:HOME`, and camera OCR matched `OK`.
- Camera OCR artifacts: `.logs/camera-ocr-20260616-081727.jpg`, `.logs/camera-ocr-20260616-081727.processed.png`, `.logs/camera-ocr-20260616-081727.txt`.
