# P0 Cloud AI Terminal

This lane is the self-developed AI terminal path. The target end state is:

```text
microphone -> host/cloud ASR -> LLM -> TTS -> screen + speaker
```

The first committed slice proves the control plane before streaming audio: the board runs a display sketch, the host relay talks to it over serial, and the response is rendered on the AMOLED. This gives us a repeatable hardware test for screen output and host/cloud integration shape while the ES7210/ES8311 audio stream is added.

## Commands

```bash
make cloud-ai-build
make cloud-ai-smoke
make cloud-ai-pipeline-smoke
make cloud-ai-cache-smoke
CLOUD_AI_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make cloud-ai-smoke
```

`make cloud-ai-smoke` uploads `sketches/cloud_ai_terminal`, waits for `CLOUD_AI_READY`, sends a mock question through `scripts/cloud-ai-relay.py`, and verifies the board acknowledges `AI_DISPLAYED`.

`make cloud-ai-pipeline-smoke` uses the same sketch and relay but drives a non-audio ASR -> LLM -> TTS state machine over serial. It sends `STATUS:LISTEN`, `ASR:<transcript>`, `STATUS:THINK`, `LLM:<response>`, `STATUS:SPEAK`, and `TTS:<tts marker>`, then verifies `PIPELINE_DONE`. This is the acceptance gate for the cloud AI protocol before real ES7210 microphone frames and ES8311 TTS playback are connected.

`make cloud-ai-cache-smoke` extends the pipeline smoke with board-local NVS cache checks. It clears the cache, writes and reads a session key, sets a session id, runs the ASR -> LLM -> TTS path, records a cloud request id, simulates one recoverable cloud error, then verifies the latest `response`, `tts`, cloud request, metrics, and `CLOUD_AI_STATE` fields are available over serial.

The relay also supports a simple HTTP mode:

```bash
python3 scripts/cloud-ai-relay.py \
  --port /dev/cu.usbmodem83101 \
  --mode http \
  --endpoint http://127.0.0.1:8787/ask \
  --question "hello"
```

The HTTP endpoint should accept `{"question":"..."}` and return JSON with `text`, `response`, or `answer`.

The pipeline relay can also use the HTTP response as the LLM result:

```bash
python3 scripts/cloud-ai-relay.py \
  --port /dev/cu.usbmodem83101 \
  --pipeline \
  --mode http \
  --endpoint http://127.0.0.1:8787/ask \
  --transcript "turn on the desk light"
```

## Serial Pipeline Contract

The board accepts:

- `STATE?` for the current UI/cache/runtime state.
- `METRICS?` for pipeline/cloud request/error counters.
- `SESSION:<id>`
- `CACHE:CLEAR`
- `CACHE:PUT:<key>=<value>`
- `CACHE:GET:<key>`
- `STATUS:<state>` for UI state such as `LISTEN`, `THINK`, or `SPEAK`.
- `ASR:<transcript>` after host or cloud speech recognition.
- `CLOUD:REQ:<id>:<provider>` before a cloud LLM request.
- `CLOUD:ERR:<code>:<message>` for recoverable cloud error reporting.
- `LLM:<response>` after the language model returns text.
- `TTS:<marker>` after the host has prepared a TTS frame or playback job.

The board emits:

- `STATUS_RX:<state>`
- `CACHE_CLEAR ok=...`
- `CACHE_PUT ok=... key=...`
- `CACHE_VALUE hit=... key=... value=...`
- `CLOUD_AI_STATE display=... cache=... status=... pipeline_count=...`
- `SESSION_SET id=...`
- `ASR_RX:<transcript>`
- `CLOUD_REQ id=... provider=...`
- `CLOUD_ERROR code=... message=...`
- `CLOUD_AI_METRICS pipeline_count=... cloud_count=... cloud_errors=...`
- `LLM_DISPLAYED:<response>`
- `TTS_READY:<marker>`
- `PIPELINE_DONE ...`

## Current Verification

- Build gate: `make cloud-ai-build`.
- Hardware gate: `make cloud-ai-smoke` uploads the sketch and validates the serial relay.
- Pipeline gate: `make cloud-ai-pipeline-smoke` validates the non-audio ASR -> LLM -> TTS serial state machine.
- Cache/cloud gate: `make cloud-ai-cache-smoke` validates local NVS cache, session id, cloud request id, cloud error metrics, and status-management commands.
- Visual gate: `CLOUD_AI_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make cloud-ai-smoke` adds camera OCR and expects the screen to contain `OK`. The serial relay still verifies the full `AI_DISPLAYED:AI OK` response.

## Verified Locally

- `make cloud-ai-build`: passed with `432371 bytes` program storage and `23064 bytes` dynamic memory.
- `make cloud-ai-smoke`: uploaded to `/dev/cu.usbmodem83101`, completed `PING`/`PONG`, `ASK_RX`, and `AI_DISPLAYED:AI OK`.
- `SKIP_BUILD=1 make cloud-ai-pipeline-smoke`: uploaded to `/dev/cu.usbmodem83101`, completed `PING`/`PONG`, `STATUS_RX:LISTEN`, `ASR_RX`, `STATUS_RX:THINK`, `LLM_DISPLAYED`, `STATUS_RX:SPEAK`, `TTS_READY`, and `PIPELINE_DONE`.
- `SKIP_BUILD=1 make cloud-ai-cache-smoke`: uploaded to `/dev/cu.usbmodem83101`, completed `CACHE_CLEAR`, `SESSION_SET`, `CACHE_PUT`, `CACHE_VALUE`, `STATE?`, pipeline, `CLOUD_REQ`, cached `response`, cached `tts`, cached `cloud_req`, `CLOUD_ERROR`, `CLOUD_AI_METRICS cloud_errors=1`, and final `CLOUD_AI_STATE status=TTS`.
- `SKIP_BUILD=1 skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh cloud-ai /Users/phodal/hardware/arduino pipeline`: passed the same non-audio pipeline through the repo Skill helper.
- `SKIP_BUILD=1 /Users/phodal/.codex/skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh cloud-ai /Users/phodal/hardware/arduino pipeline`: passed the same non-audio pipeline through the global Skill helper.
- `SKIP_BUILD=1 skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh cloud-ai /Users/phodal/hardware/arduino cache`: passed the same cache gate through the repo Skill helper.
- `SKIP_BUILD=1 /Users/phodal/.codex/skills/waveshare-esp32s3-amoled/scripts/waveshare-arduino-cli.sh cloud-ai /Users/phodal/hardware/arduino cache`: passed the same cache gate through the global Skill helper.
- `CLOUD_AI_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 CAMERA_DEVICE=0 CAMERA_SIZE=1280x720 OCR_ENGINE=vision CLOUD_AI_TIMEOUT=20 make cloud-ai-smoke`: passed serial relay and camera OCR.
- Latest visual artifact: `.logs/camera-ocr-20260613-225433.jpg`.
- `make hardware-smoke-suite HARDWARE_SMOKE_ARGS="--target cloud-ai-terminal --skip-build --per-target-timeout 240 --max-failures 1"`: passed with summary `.logs/hardware-smoke-suite/20260614-060731/summary.json`.
- Observed relay result: `{"status": "ok", "mode": "mock", "pipeline": true, "cache": true, "response": "AI OK", "tts": "tts frame ready", "session": "codex-session", "request_id": "req-codex-1"}`.

## Remaining Hardware Work

- The non-audio cloud terminal control plane is verified. Physical ES7210 microphone capture, ES8311 TTS playback, and acoustic validation remain intentionally gated by the audio lanes and should not be run late at night.
