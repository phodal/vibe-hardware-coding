#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <Preferences.h>
#include <Wire.h>
#include <ctype.h>
#include "pin_config.h"

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
  LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);

Arduino_CO5300 *gfx = new Arduino_CO5300(
  bus, LCD_RESET, 0, LCD_WIDTH, LCD_HEIGHT, 6, 0, 0, 0);

Preferences prefs;

#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 0
#endif

String inputLine;
uint32_t frame = 0;
uint32_t pipelineCount = 0;
uint32_t cloudRequestCount = 0;
uint32_t cloudErrorCount = 0;
bool displayReady = false;
bool cacheReady = false;
String lastTranscript = "";
String lastResponse = "";
String lastTts = "";
String lastStatus = "READY";
String sessionId = "local";
String lastCloudRequest = "-";
String lastCloudError = "-";

void centerText(const String &text, int16_t y, uint8_t size, uint16_t color) {
  int16_t x1;
  int16_t y1;
  uint16_t w;
  uint16_t h;
  gfx->setTextSize(size);
  gfx->getTextBounds(text, 0, y, &x1, &y1, &w, &h);
  gfx->setCursor((LCD_WIDTH - w) / 2, y);
  gfx->setTextColor(color, RGB565_BLACK);
  gfx->print(text);
}

String fitLine(String text, size_t maxLen) {
  text.trim();
  if (text.length() <= maxLen) {
    return text;
  }
  return text.substring(0, maxLen - 3) + "...";
}

void drawFrame(const String &status, const String &response) {
  if (!displayReady) {
    return;
  }

  gfx->fillScreen(RGB565_BLACK);
  gfx->drawRect(8, 8, LCD_WIDTH - 16, LCD_HEIGHT - 16, RGB565_CYAN);
  gfx->drawRect(14, 14, LCD_WIDTH - 28, LCD_HEIGHT - 28, RGB565_BLUE);

  centerText("Cloud AI", 46, 4, RGB565_CYAN);

  gfx->setTextSize(2);
  gfx->setTextColor(RGB565_YELLOW, RGB565_BLACK);
  gfx->setCursor(34, 126);
  gfx->print("Status: ");
  gfx->println(fitLine(status, 18));

  centerText(fitLine(response, 10), 202, 6, RGB565_WHITE);

  gfx->setTextSize(2);
  gfx->setTextColor(RGB565_GREEN, RGB565_BLACK);
  gfx->setCursor(34, 362);
  gfx->print("Serial relay ready");
}

bool validCacheKey(const String &key) {
  if (key.length() == 0 || key.length() > 15) {
    return false;
  }
  for (size_t i = 0; i < key.length(); i++) {
    char c = key.charAt(i);
    if (!isalnum(c) && c != '_') {
      return false;
    }
  }
  return true;
}

void cachePut(const String &key, const String &value) {
  if (!cacheReady || !validCacheKey(key)) {
    Serial.print("CACHE_PUT ok=0 key=");
    Serial.println(fitLine(key, 16));
    Serial.flush();
    return;
  }

  bool ok = prefs.putString(key.c_str(), value) > 0;
  Serial.print("CACHE_PUT ok=");
  Serial.print(ok ? 1 : 0);
  Serial.print(" key=");
  Serial.print(fitLine(key, 16));
  Serial.print(" bytes=");
  Serial.println(value.length());
  Serial.flush();
}

void cacheGet(const String &key) {
  if (!cacheReady || !validCacheKey(key)) {
    Serial.print("CACHE_VALUE hit=0 key=");
    Serial.print(fitLine(key, 16));
    Serial.println(" value=");
    Serial.flush();
    return;
  }

  bool hit = prefs.isKey(key.c_str());
  String value = hit ? prefs.getString(key.c_str(), "") : "";
  Serial.print("CACHE_VALUE hit=");
  Serial.print(hit ? 1 : 0);
  Serial.print(" key=");
  Serial.print(fitLine(key, 16));
  Serial.print(" value=");
  Serial.println(fitLine(value, 80));
  Serial.flush();
}

void saveRuntimeState() {
  if (!cacheReady) {
    return;
  }
  prefs.putString("status", lastStatus);
  prefs.putString("transcript", lastTranscript);
  prefs.putString("response", lastResponse);
  prefs.putString("tts", lastTts);
  prefs.putString("session", sessionId);
  prefs.putString("cloud_req", lastCloudRequest);
  prefs.putString("cloud_err", lastCloudError);
  prefs.putUInt("pipe_count", pipelineCount);
  prefs.putUInt("cloud_count", cloudRequestCount);
  prefs.putUInt("cloud_errors", cloudErrorCount);
}

void emitDisplayAck(const char *prefix, const String &value) {
  Serial.print(prefix);
  Serial.println(fitLine(value, 64));
  Serial.flush();
}

void emitState() {
  Serial.print("CLOUD_AI_STATE display=");
  Serial.print(displayReady ? 1 : 0);
  Serial.print(" cache=");
  Serial.print(cacheReady ? 1 : 0);
  Serial.print(" status=");
  Serial.print(fitLine(lastStatus, 18));
  Serial.print(" pipeline_count=");
  Serial.print(pipelineCount);
  Serial.print(" cloud_count=");
  Serial.print(cloudRequestCount);
  Serial.print(" cloud_errors=");
  Serial.print(cloudErrorCount);
  Serial.print(" session=");
  Serial.print(fitLine(sessionId, 18));
  Serial.print(" transcript=");
  Serial.print(fitLine(lastTranscript, 24));
  Serial.print(" response=");
  Serial.print(fitLine(lastResponse, 24));
  Serial.print(" tts=");
  Serial.println(fitLine(lastTts, 24));
  Serial.flush();
}

void emitMetrics() {
  Serial.print("CLOUD_AI_METRICS pipeline_count=");
  Serial.print(pipelineCount);
  Serial.print(" cloud_count=");
  Serial.print(cloudRequestCount);
  Serial.print(" cloud_errors=");
  Serial.print(cloudErrorCount);
  Serial.print(" session=");
  Serial.print(fitLine(sessionId, 18));
  Serial.print(" last_request=");
  Serial.print(fitLine(lastCloudRequest, 24));
  Serial.print(" last_error=");
  Serial.println(fitLine(lastCloudError, 24));
  Serial.flush();
}

void processLine(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  if (line == "PING") {
    Serial.println("PONG");
    Serial.flush();
    return;
  }

  if (line == "STATE?") {
    emitState();
    return;
  }

  if (line == "CACHE:CLEAR") {
    bool ok = cacheReady && prefs.clear();
    lastTranscript = "";
    lastResponse = "";
    lastTts = "";
    lastStatus = "READY";
    lastCloudRequest = "-";
    lastCloudError = "-";
    pipelineCount = 0;
    cloudRequestCount = 0;
    cloudErrorCount = 0;
    Serial.print("CACHE_CLEAR ok=");
    Serial.println(ok ? 1 : 0);
    Serial.flush();
    drawFrame(lastStatus, "AI OK");
    return;
  }

  if (line.startsWith("SESSION:")) {
    sessionId = line.substring(8);
    sessionId.trim();
    if (sessionId.length() == 0) {
      sessionId = "local";
    }
    saveRuntimeState();
    Serial.print("SESSION_SET id=");
    Serial.println(fitLine(sessionId, 32));
    Serial.flush();
    return;
  }

  if (line == "METRICS?") {
    emitMetrics();
    return;
  }

  if (line.startsWith("CLOUD:REQ:")) {
    String payload = line.substring(10);
    int separator = payload.indexOf(':');
    String requestId = separator >= 0 ? payload.substring(0, separator) : payload;
    String provider = separator >= 0 ? payload.substring(separator + 1) : "mock";
    requestId.trim();
    provider.trim();
    cloudRequestCount++;
    lastCloudRequest = requestId;
    lastStatus = "CLOUD";
    saveRuntimeState();
    drawFrame("CLOUD", provider);
    Serial.print("CLOUD_REQ id=");
    Serial.print(fitLine(requestId, 24));
    Serial.print(" provider=");
    Serial.print(fitLine(provider, 24));
    Serial.print(" count=");
    Serial.println(cloudRequestCount);
    Serial.flush();
    return;
  }

  if (line.startsWith("CLOUD:ERR:")) {
    String payload = line.substring(10);
    int separator = payload.indexOf(':');
    String code = separator >= 0 ? payload.substring(0, separator) : "ERR";
    String message = separator >= 0 ? payload.substring(separator + 1) : payload;
    code.trim();
    message.trim();
    cloudErrorCount++;
    lastCloudError = code + ":" + message;
    lastStatus = "ERROR";
    saveRuntimeState();
    drawFrame("ERROR", code);
    Serial.print("CLOUD_ERROR code=");
    Serial.print(fitLine(code, 16));
    Serial.print(" message=");
    Serial.print(fitLine(message, 48));
    Serial.print(" count=");
    Serial.println(cloudErrorCount);
    Serial.flush();
    return;
  }

  if (line.startsWith("CACHE:PUT:")) {
    String payload = line.substring(10);
    int separator = payload.indexOf('=');
    if (separator <= 0) {
      Serial.println("CACHE_PUT ok=0 key=");
      Serial.flush();
      return;
    }
    cachePut(payload.substring(0, separator), payload.substring(separator + 1));
    return;
  }

  if (line.startsWith("CACHE:GET:")) {
    cacheGet(line.substring(10));
    return;
  }

  if (line.startsWith("ASK:")) {
    String question = line.substring(4);
    lastTranscript = question;
    lastStatus = "THINK";
    saveRuntimeState();
    drawFrame("THINK", "...");
    emitDisplayAck("ASK_RX:", question);
    return;
  }

  if (line.startsWith("ASR:")) {
    String transcript = line.substring(4);
    lastTranscript = transcript;
    lastStatus = "ASR";
    saveRuntimeState();
    drawFrame("ASR", transcript);
    emitDisplayAck("ASR_RX:", transcript);
    return;
  }

  if (line.startsWith("AI:")) {
    String response = line.substring(3);
    lastResponse = response;
    lastStatus = "DONE";
    saveRuntimeState();
    drawFrame("DONE", response);
    emitDisplayAck("AI_DISPLAYED:", response);
    return;
  }

  if (line.startsWith("LLM:")) {
    String response = line.substring(4);
    lastResponse = response;
    lastStatus = "LLM";
    saveRuntimeState();
    drawFrame("LLM", response);
    emitDisplayAck("LLM_DISPLAYED:", response);
    return;
  }

  if (line.startsWith("TTS:")) {
    String tts = line.substring(4);
    lastTts = tts;
    pipelineCount++;
    lastStatus = "TTS";
    saveRuntimeState();
    drawFrame("TTS", lastResponse.length() > 0 ? lastResponse : tts);
    emitDisplayAck("TTS_READY:", tts);
    Serial.print("PIPELINE_DONE count=");
    Serial.print(pipelineCount);
    Serial.print(" transcript=");
    Serial.print(fitLine(lastTranscript, 24));
    Serial.print(" response=");
    Serial.print(fitLine(lastResponse, 24));
    Serial.print(" tts=");
    Serial.println(fitLine(lastTts, 24));
    Serial.flush();
    return;
  }

  if (line.startsWith("STATUS:")) {
    String status = line.substring(7);
    lastStatus = status;
    saveRuntimeState();
    drawFrame(status, "WAIT");
    Serial.print("STATUS_RX:");
    Serial.println(fitLine(status, 64));
    Serial.flush();
    return;
  }

  Serial.print("UNKNOWN_CMD:");
  Serial.println(fitLine(line, 64));
  Serial.flush();
}

void setup() {
  Serial.begin(115200);
  uint32_t serialWaitStart = millis();
  while (!Serial && (millis() - serialWaitStart < 5000)) {
    delay(100);
  }

  Serial.println("cloud_ai_terminal boot");
  Serial.flush();

  Wire.begin(IIC_SDA, IIC_SCL);
  cacheReady = prefs.begin("cloudai", false);
  if (cacheReady) {
    lastStatus = prefs.getString("status", "READY");
    lastTranscript = prefs.getString("transcript", "");
    lastResponse = prefs.getString("response", "");
    lastTts = prefs.getString("tts", "");
    sessionId = prefs.getString("session", "local");
    lastCloudRequest = prefs.getString("cloud_req", "-");
    lastCloudError = prefs.getString("cloud_err", "-");
    pipelineCount = prefs.getUInt("pipe_count", 0);
    cloudRequestCount = prefs.getUInt("cloud_count", 0);
    cloudErrorCount = prefs.getUInt("cloud_errors", 0);
  }

  if (!gfx->begin()) {
    Serial.println("cloud_ai_terminal gfx begin failed");
    Serial.flush();
    return;
  }

  gfx->setBrightness(200);
  gfx->setRotation(DISPLAY_ROTATION);
  displayReady = true;
  drawFrame(lastStatus.length() > 0 ? lastStatus : "READY", lastResponse.length() > 0 ? lastResponse : "AI OK");

  Serial.println("cloud_ai_terminal display ready");
  Serial.println("CLOUD_AI_READY");
  emitState();
  Serial.flush();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      processLine(inputLine);
      inputLine = "";
    } else if (c != '\r') {
      inputLine += c;
      if (inputLine.length() > 160) {
        inputLine = inputLine.substring(inputLine.length() - 160);
      }
    }
  }

  if ((frame % 20) == 0) {
    Serial.print("cloud_ai_terminal frame=");
    Serial.println(frame);
    if ((frame % 100) == 0) {
      Serial.println("CLOUD_AI_READY");
    }
    Serial.flush();
  }
  frame++;
  delay(50);
}
