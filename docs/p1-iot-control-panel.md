# P1 IoT Control Panel

The `iot_control_panel` sketch is the first Home Assistant / MQTT / HTTP control-panel slice for the Waveshare ESP32-S3-Touch-AMOLED-1.75C. It uses a serial protocol first so the UI, touch behavior, and state machine can be validated without Wi-Fi credentials or a live smart-home server.

## What It Proves

- The AMOLED can render a compact multi-page IoT control panel.
- The CST9217 touch controller initializes and can cycle device selection.
- Device state changes, Home Assistant service calls, scene changes, MQTT-style inbound events, and HTTP-style outbound actions can update the same state model.
- Automation can validate the panel with deterministic serial commands before replacing the host relay with direct Wi-Fi/MQTT/HTTP integrations.

## Commands

```bash
make iot-panel-build
make iot-panel-smoke
make iot-panel-relay-smoke
IOT_PANEL_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make iot-panel-smoke
```

The smoke script uploads the sketch, waits for `IOT_READY`, sends device, Home Assistant, MQTT, HTTP, and scene commands, then verifies `IOT_STATE`, `IOT_DEVICE`, `IOT_HA`, `IOT_MQTT`, and `IOT_HTTP` output.

`make iot-panel-relay-smoke` uploads the same sketch and runs `scripts/iot-panel-relay.py`. The relay maps mock, JSON-file, or HTTP smart-home events into the board serial protocol. Home Assistant events use the explicit `IOT:HA` command and must produce board-side `IOT_HA` output plus an incremented `ha=` state counter. This is the host-side adapter gate before using real Home Assistant, MQTT broker, or HTTP controller credentials.

Relay payload shape:

```json
{
  "home_assistant": [
    {"service": "light.turn_on", "index": 0, "state": "ON"},
    {"service": "switch.toggle", "index": 1, "toggle": true},
    {"service": "climate.set_temperature", "index": 3, "value": 23}
  ],
  "mqtt": [{"topic": "home/door", "index": 2, "state": "OPEN"}],
  "http": [{"method": "POST", "path": "/api/light/turn_on", "status": 200}],
  "scene": "NIGHT"
}
```

## Serial Protocol

- `PING` returns `PONG`.
- `PAGE:HOME`, `PAGE:DEVICES`, `PAGE:SCENE`, and `PAGE:LOG` switch pages.
- `IOT:SELECT:<index>` selects a device card.
- `IOT:SET:<index>:<state>` sets a device state.
- `IOT:TOGGLE:<index>` toggles a light/switch/lock.
- `IOT:VALUE:<index>:<value>` sets a numeric device value such as climate temperature.
- `IOT:HA:<service>:<index>:<payload>` applies a Home Assistant-style service call and emits `IOT_HA`.
- `IOT:MQTT:<topic>:<index>:<state>` simulates an inbound MQTT update.
- `IOT:HTTP:<method>:<path>:<status>` records an outbound HTTP action.
- `SCENE:<HOME|AWAY|NIGHT>` applies a basic scene.
- `STATE?` emits `IOT_STATE`.

## Notes

This is a control-plane and UI slice, not yet a direct network integration. The host relay bridges Home Assistant, MQTT, or HTTP-style events into this protocol; after that is stable, the same state model can move into direct Wi-Fi firmware.

## Verified Locally

- `make iot-panel-build`: passed.
- `make iot-panel-smoke`: uploaded to `/dev/cu.usbmodem83101` and validated direct serial commands for devices, explicit Home Assistant service calls, MQTT, HTTP, and scenes.
- `SKIP_BUILD=1 make iot-panel-relay-smoke`: uploaded to `/dev/cu.usbmodem83101` and validated mock Home Assistant service calls, MQTT, HTTP, and scene events through the host relay.
- `make hardware-smoke-suite HARDWARE_SMOKE_ARGS="--target iot-panel --skip-build --per-target-timeout 240 --max-failures 1"`: passed with summary `.logs/hardware-smoke-suite/20260614-053656/summary.json`.
- `SKIP_BUILD=1 skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh iot-panel /Users/phodal/hardware/arduino relay`: passed through the repo Skill helper.
- `SKIP_BUILD=1 /Users/phodal/.codex/skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh iot-panel /Users/phodal/hardware/arduino relay`: passed through the global Skill helper.
