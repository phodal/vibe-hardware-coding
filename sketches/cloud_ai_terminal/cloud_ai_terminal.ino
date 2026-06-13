#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <Wire.h>
#include "pin_config.h"

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
  LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);

Arduino_CO5300 *gfx = new Arduino_CO5300(
  bus, LCD_RESET, 0, LCD_WIDTH, LCD_HEIGHT, 6, 0, 0, 0);

#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 0
#endif

String inputLine;
uint32_t frame = 0;
uint32_t pipelineCount = 0;
bool displayReady = false;
String lastTranscript = "";
String lastResponse = "";
String lastTts = "";

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

void emitDisplayAck(const char *prefix, const String &value) {
  Serial.print(prefix);
  Serial.println(fitLine(value, 64));
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

  if (line.startsWith("ASK:")) {
    String question = line.substring(4);
    lastTranscript = question;
    drawFrame("THINK", "...");
    emitDisplayAck("ASK_RX:", question);
    return;
  }

  if (line.startsWith("ASR:")) {
    String transcript = line.substring(4);
    lastTranscript = transcript;
    drawFrame("ASR", transcript);
    emitDisplayAck("ASR_RX:", transcript);
    return;
  }

  if (line.startsWith("AI:")) {
    String response = line.substring(3);
    lastResponse = response;
    drawFrame("DONE", response);
    emitDisplayAck("AI_DISPLAYED:", response);
    return;
  }

  if (line.startsWith("LLM:")) {
    String response = line.substring(4);
    lastResponse = response;
    drawFrame("LLM", response);
    emitDisplayAck("LLM_DISPLAYED:", response);
    return;
  }

  if (line.startsWith("TTS:")) {
    String tts = line.substring(4);
    lastTts = tts;
    pipelineCount++;
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

  if (!gfx->begin()) {
    Serial.println("cloud_ai_terminal gfx begin failed");
    Serial.flush();
    return;
  }

  gfx->setBrightness(200);
  gfx->setRotation(DISPLAY_ROTATION);
  displayReady = true;
  drawFrame("READY", "AI OK");

  Serial.println("cloud_ai_terminal display ready");
  Serial.println("CLOUD_AI_READY");
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
