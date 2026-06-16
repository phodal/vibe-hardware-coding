# P1 Power Lifecycle Probe

## Purpose

`sketches/power_lifecycle_probe` validates the AXP2101 power path and a serial-preserving low-power lifecycle for the Waveshare ESP32-S3 Touch AMOLED 1.75C.

The probe is intentionally silent. It does not use the host microphone, speaker, or board audio path.

## Commands

```bash
make power-lifecycle-build
make power-lifecycle-smoke
POWER_REQUIRE_BATTERY=1 make power-lifecycle-smoke
POWER_LIFECYCLE_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make power-lifecycle-smoke
```

`POWER_REQUIRE_BATTERY=1` should only be used when a battery is connected. The default smoke accepts USB-only benches because the battery connector may be unused.

## Serial Contract

The sketch emits:

- `POWER_READY` or `POWER_PARTIAL`
- `POWER_STATE display=... pmu=... mode=... brightness=...`
- `POWER_PROFILE capacity_mah=... active_ma=... dim_ma=... standby_ma=...`
- `POWER_SAMPLE system_mv=... vbus_mv=... batt_mv=... battery_connected=... estimate_min=...`
- `POWER_MODE mode=... brightness=... source=...`

The host checker drives:

- `PING`
- `PROFILE?`
- `SAMPLE?`
- `MODE:DIM`
- `MODE:STANDBY`
- `MODE:ACTIVE`
- `BRIGHT:96`
- `CAPACITY:500`
- `LOAD:180,60,15`
- `STATE?`

## Acceptance

`make power-lifecycle-smoke` passes when:

- the AMOLED display and AXP2101 PMU initialize
- system voltage is at least `POWER_MIN_SYSTEM_MV` or 2500 mV by default
- DIM, STANDBY, and ACTIVE transitions are observed
- standby wakes back to ACTIVE over serial
- brightness, capacity, and load profile commands take effect
- the runtime estimate remains nonnegative

## Notes

The automated `STANDBY` mode dims the display to zero while keeping USB serial alive. It is not a true ESP32 deep-sleep proof. A future true low-power pass should use reset/wake evidence and a separate current measurement path because deep sleep can intentionally disconnect the serial session.

The visual smoke uses color preprocessing plus a screen-centered focus/exposure point by default because the white `OK` marker can blur under the webcam when captured with the generic gray OCR path.

## Verified Locally

- `make hardware-smoke-suite HARDWARE_SMOKE_ARGS="--targets offline-voice,lvgl-visual-agent,power-lifecycle,esp-claw-agent,tinyml-imu --skip-build --per-target-timeout 240 --max-failures 1"`: uploaded `power-lifecycle-smoke` to `/dev/cu.usbmodem83101` and passed the AXP2101 lifecycle gate.
- Latest suite summary: `.logs/hardware-smoke-suite/20260614-044244/summary.json`.
- Latest target log: `.logs/hardware-smoke-suite/20260614-044244/power-lifecycle.log`.
- Observed summary: `power_lifecycle_summary modes=ACTIVE,DIM,STANDBY system_mv=4306 vbus_mv=5166 batt_mv=4078 battery_connected=1 estimate_min=166 mode_changes=3 wake_count=1`.
- `POWER_LIFECYCLE_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 POWER_LIFECYCLE_SECONDS=4 CAMERA_CAPTURE_TIMEOUT=8 make power-lifecycle-smoke`: uploaded to `/dev/cu.usbmodem83101`, validated DIM/STANDBY/ACTIVE, brightness, capacity, load profile, wake, and runtime estimate over serial, then captured the board screen for OCR.
- Focused camera OCR pass on the same screen: `OCR_EXPECTED=OK CAMERA_CAPTURE_TIMEOUT=8 CAMERA_FOCUS_POINT=0.48,0.52 CAMERA_EXPOSURE_POINT=0.48,0.52 OCR_PREPROCESS_MODE=color OCR_SCALE_WIDTH=2400 ./scripts/camera-ocr.sh`.
- Camera OCR artifacts: `.logs/camera-ocr-20260616-084122.jpg`, `.logs/camera-ocr-20260616-084122.processed.png`, `.logs/camera-ocr-20260616-084122.txt`.
- Latest visual build size: `442967 bytes` program storage and `22992 bytes` dynamic memory.
