# P1 IoT Control Panel

The `iot_control_panel` sketch is the first Home Assistant / MQTT / HTTP control-panel slice for the Waveshare ESP32-S3-Touch-AMOLED-1.75C. It uses a serial protocol first so the UI, touch behavior, and state machine can be validated without Wi-Fi credentials or a live smart-home server.

## What It Proves

- The AMOLED can render a compact multi-page IoT control panel.
- The CST9217 touch controller initializes and can cycle device selection.
- Device state changes, scene changes, MQTT-style inbound events, and HTTP-style outbound actions can update the same state model.
- Automation can validate the panel with deterministic serial commands before replacing the host relay with direct Wi-Fi/MQTT/HTTP integrations.

## Commands

```bash
make iot-panel-build
make iot-panel-smoke
IOT_PANEL_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make iot-panel-smoke
```

The smoke script uploads the sketch, waits for `IOT_READY`, sends device, MQTT, HTTP, and scene commands, then verifies `IOT_STATE`, `IOT_DEVICE`, `IOT_MQTT`, and `IOT_HTTP` output.

## Serial Protocol

- `PING` returns `PONG`.
- `PAGE:HOME`, `PAGE:DEVICES`, `PAGE:SCENE`, and `PAGE:LOG` switch pages.
- `IOT:SELECT:<index>` selects a device card.
- `IOT:SET:<index>:<state>` sets a device state.
- `IOT:TOGGLE:<index>` toggles a light/switch/lock.
- `IOT:VALUE:<index>:<value>` sets a numeric device value such as climate temperature.
- `IOT:MQTT:<topic>:<index>:<state>` simulates an inbound MQTT update.
- `IOT:HTTP:<method>:<path>:<status>` records an outbound HTTP action.
- `SCENE:<HOME|AWAY|NIGHT>` applies a basic scene.
- `STATE?` emits `IOT_STATE`.

## Notes

This is a control-plane and UI slice, not yet a direct network integration. A future host relay can bridge real Home Assistant, MQTT, or HTTP events into this protocol; after that is stable, the same state model can move into direct Wi-Fi firmware.
