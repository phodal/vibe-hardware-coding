# Web AI Button Evidence 20260614-130537

This evidence pack records the Phodal-branded local Mac webserver plus ESP32-S3 Wi-Fi AI button validation chain.

## Result

- Build: passed
- Upload: passed
- Touch controller: ready
- Pre-config touch guard: passed
- Wi-Fi join: passed
- Local HTTP AI trigger: passed
- Local server keepalive: passed
- Camera OCR: passed
- Destructive: 0
- Audio: 0

## Serial Evidence

```text
WEB_AI_WIFI status=ok connected=1 rssi=-70 ip=192.168.31.65
WEB_AI_TRIGGER source=serial count=1 prompt_chars=12
WEB_AI_RESPONSE status=ok code=200 chars=14 text=AI OK from Mac
WEB_AI_STATE display=1 touch=1 wifi=1 triggers=1 touches=0 ip=192.168.31.65
web_ai_button_summary connected=1 ip=192.168.31.65 triggers=1 touch=1 expect='AI OK'
web_ai_server_kept_alive pid=95923 log=/Users/phodal/hardware/arduino/.logs/web-ai-server.log endpoint=http://192.168.31.197:8787/ask
```

The keepalive server was verified after the smoke with `GET /health` returning HTTP 200.

## Camera OCR

The final firmware renders `Phodal` above the `ASK AI` button. Camera OCR was run with:

```bash
OCR_EXPECTED=Phodal OCR_ROTATE=180 LOG_DIR=.logs/web-ai-button-phodal-final ./scripts/camera-ocr.sh
```

OCR output included:

```text
Phodal
AS AI
```

## Artifacts

- Raw camera image: `camera-ocr-20260614-130537.jpg`
- Processed OCR image: `camera-ocr-20260614-130537.processed.png`
- OCR text: `camera-ocr-20260614-130537.txt`
- Local server log: `server.log`

## Interpretation

The automated smoke proves the board can join Wi-Fi, reach the Mac HTTP server, trigger the local AI endpoint, and display the response. The button no longer treats pre-config taps as AI failures; the local server can be kept alive with `WEB_AI_KEEP_SERVER=1` for manual tap testing after automation exits.
