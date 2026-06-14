# Web AI Button Qoder Evidence 20260614-145545

This evidence pack records the Qoder-branded local Mac webserver plus ESP32-S3 Wi-Fi AI button validation chain.

## Result

- Build: passed
- Upload: passed
- Touch controller: ready
- Wi-Fi join: passed
- Local HTTP AI trigger: passed
- Non-visual Make smoke: passed after adding a Wi-Fi settle delay in the checker
- Local server keepalive: passed
- Camera capture: passed
- Camera OCR: partial; Vision read the large visual marker as `Bol` instead of exact `OK`
- Destructive: 0
- Audio: 0

## Serial Evidence

```text
WEB_AI_WIFI status=ok connected=1 rssi=-73 ip=<esp32-lan-ip>
WEB_AI_TRIGGER source=serial count=1 prompt_chars=12
WEB_AI_RESPONSE status=ok code=200 chars=17 text=Qoder OK from Mac
WEB_AI_STATE display=1 touch=1 wifi=1 triggers=1 touches=0 ip=<esp32-lan-ip>
web_ai_button_summary connected=1 ip=<esp32-lan-ip> triggers=1 touch=1 expect='Qoder OK'
web_ai_server_kept_alive pid=94532 log=/Users/phodal/hardware/arduino/.logs/web-ai-server.log endpoint=http://<mac-lan-ip>:8787/ask
```

## Camera Evidence

The final firmware renders `Qoder` plus a large `OK` marker. The raw camera view is upside down for the current camera mount, so this pack includes both the raw capture and a `qoder-ok-upright.jpg` preview rotated 180 degrees for human inspection.

OCR was run with:

```bash
WEB_AI_KEEP_SERVER=1 WEB_AI_BUTTON_VISUAL_SMOKE=1 OCR_ROTATE=180 make web-ai-button-smoke
```

OCR output:

```text
Bol
```

## Artifacts

- Raw camera image: `camera-ocr-20260614-145545.jpg`
- Upright preview: `qoder-ok-upright.jpg`
- Processed OCR image: `camera-ocr-20260614-145545.processed.png`
- OCR text: `camera-ocr-20260614-145545.txt`
- Local server log: `server.log`

## Interpretation

The firmware, Wi-Fi join, local HTTP request, and AI response display are verified through serial and server logs. The camera saved a usable Qoder screenshot, but exact OCR remains sensitive to focus, orientation, and AMOLED glow; do not claim exact visual OCR success from this run.
