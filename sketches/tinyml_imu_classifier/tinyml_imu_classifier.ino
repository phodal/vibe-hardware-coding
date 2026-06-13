#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <SensorQMI8658.hpp>
#include <Wire.h>
#include <math.h>
#include <string.h>
#include "pin_config.h"

#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 0
#endif

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
  LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);

Arduino_CO5300 *gfx = new Arduino_CO5300(
  bus, LCD_RESET, 0, LCD_WIDTH, LCD_HEIGHT, 6, 0, 0, 0);

SensorQMI8658 qmi;

struct ImuSample {
  float ax;
  float ay;
  float az;
  float gx;
  float gy;
  float gz;
};

struct Classification {
  const char *label;
  float confidence;
  const char *source;
};

bool displayReady = false;
bool imuReady = false;
bool liveMode = true;
uint32_t frame = 0;
uint32_t inferenceCount = 0;
uint32_t injectedCount = 0;
String serialBuffer;
ImuSample sample = {0, 0, 1, 0, 0, 0};
Classification lastClassification = {"REST", 0.99f, "boot"};

float magnitude3(float x, float y, float z) {
  return sqrtf(x * x + y * y + z * z);
}

float accMagnitude(const ImuSample &item) {
  return magnitude3(item.ax, item.ay, item.az);
}

float gyroMagnitude(const ImuSample &item) {
  return magnitude3(item.gx, item.gy, item.gz);
}

float maxAbsAxis(const ImuSample &item) {
  return max(max(fabsf(item.ax), fabsf(item.ay)), fabsf(item.az));
}

Classification classify(const ImuSample &item, const char *source) {
  float amag = accMagnitude(item);
  float gmag = gyroMagnitude(item);
  float dominant = maxAbsAxis(item);
  float confidence = fminf(0.99f, fmaxf(0.50f, dominant / fmaxf(amag, 0.01f)));

  if (gmag > 120.0f || fabsf(amag - 1.0f) > 0.55f) {
    return {"SHAKE", fminf(0.99f, fmaxf(0.65f, gmag / 220.0f)), source};
  }
  if (item.ax < -0.55f) {
    return {"TILT_LEFT", confidence, source};
  }
  if (item.ax > 0.55f) {
    return {"TILT_RIGHT", confidence, source};
  }
  if (item.ay > 0.65f) {
    return {"FACE_UP", confidence, source};
  }
  return {"REST", fminf(0.99f, fmaxf(0.60f, item.az)), source};
}

void centerText(const char *text, int16_t y, uint8_t size, uint16_t color) {
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

uint16_t labelColor(const char *label) {
  if (strcmp(label, "SHAKE") == 0) {
    return RGB565_RED;
  }
  if (strncmp(label, "TILT", 4) == 0) {
    return RGB565_YELLOW;
  }
  return RGB565_GREEN;
}

void drawClassifierScreen() {
  if (!displayReady) {
    return;
  }

  gfx->fillScreen(RGB565_BLACK);
  gfx->drawRect(8, 8, LCD_WIDTH - 16, LCD_HEIGHT - 16, labelColor(lastClassification.label));
  centerText("TINY", 42, 6, RGB565_CYAN);
  centerText("OK", 124, 8, RGB565_WHITE);
  centerText(lastClassification.label, 236, 4, labelColor(lastClassification.label));

  gfx->setTextSize(2);
  gfx->setTextColor(RGB565_GREEN, RGB565_BLACK);
  gfx->setCursor(48, 326);
  gfx->print("conf=");
  gfx->print(lastClassification.confidence, 2);
  gfx->setCursor(48, 360);
  gfx->print("src=");
  gfx->print(lastClassification.source);
  gfx->setCursor(48, 394);
  gfx->print("n=");
  gfx->print(inferenceCount);
}

void emitModel() {
  Serial.println("TINYML_MODEL name=imu_baseline type=centroid_rule classes=REST,TILT_LEFT,TILT_RIGHT,FACE_UP,SHAKE features=ax,ay,az,gx,gy,gz");
  Serial.flush();
}

void emitClassification(const ImuSample &item, const Classification &classification) {
  Serial.print("TINYML_CLASS source=");
  Serial.print(classification.source);
  Serial.print(" label=");
  Serial.print(classification.label);
  Serial.print(" confidence=");
  Serial.print(classification.confidence, 3);
  Serial.print(" ax=");
  Serial.print(item.ax, 3);
  Serial.print(" ay=");
  Serial.print(item.ay, 3);
  Serial.print(" az=");
  Serial.print(item.az, 3);
  Serial.print(" gx=");
  Serial.print(item.gx, 3);
  Serial.print(" gy=");
  Serial.print(item.gy, 3);
  Serial.print(" gz=");
  Serial.print(item.gz, 3);
  Serial.print(" amag=");
  Serial.print(accMagnitude(item), 3);
  Serial.print(" gmag=");
  Serial.println(gyroMagnitude(item), 3);
  Serial.flush();
}

void runInference(const ImuSample &item, const char *source) {
  sample = item;
  lastClassification = classify(item, source);
  inferenceCount++;
  emitClassification(item, lastClassification);
  drawClassifierScreen();
}

bool parseSamplePayload(const String &payload, ImuSample &out) {
  float values[6] = {0, 0, 0, 0, 0, 0};
  int start = 0;
  for (int i = 0; i < 6; i++) {
    int end = payload.indexOf(',', start);
    String token = end >= 0 ? payload.substring(start, end) : payload.substring(start);
    token.trim();
    if (token.length() == 0) {
      return false;
    }
    values[i] = token.toFloat();
    start = end + 1;
    if (end < 0 && i < 5) {
      return false;
    }
  }
  out = {values[0], values[1], values[2], values[3], values[4], values[5]};
  return true;
}

void setupDisplay() {
  if (!gfx->begin()) {
    Serial.println("TINYML_DISPLAY_FAILED");
    Serial.flush();
    return;
  }
  gfx->setRotation(DISPLAY_ROTATION);
  gfx->setBrightness(200);
  displayReady = true;
  drawClassifierScreen();
}

void setupImu() {
  imuReady = qmi.begin(Wire, QMI8658_L_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!imuReady) {
    Serial.println("TINYML_IMU_FAILED");
    Serial.flush();
    return;
  }

  qmi.configAccelerometer(
    SensorQMI8658::ACC_RANGE_4G,
    SensorQMI8658::ACC_ODR_125Hz,
    SensorQMI8658::LPF_MODE_0);
  qmi.configGyroscope(
    SensorQMI8658::GYR_RANGE_256DPS,
    SensorQMI8658::GYR_ODR_112_1Hz,
    SensorQMI8658::LPF_MODE_0);
  qmi.enableAccelerometer();
  qmi.enableGyroscope();
  Serial.println("TINYML_IMU_READY");
  Serial.flush();
}

void updateLiveSample() {
  if (!imuReady || !liveMode || !qmi.getDataReady()) {
    return;
  }

  IMUdata acc = {0, 0, 0};
  IMUdata gyr = {0, 0, 0};
  qmi.getAccelerometer(acc.x, acc.y, acc.z);
  qmi.getGyroscope(gyr.x, gyr.y, gyr.z);
  sample = {acc.x, acc.y, acc.z, gyr.x, gyr.y, gyr.z};
}

void emitStatus() {
  Serial.print("TINYML_STATUS frame=");
  Serial.print(frame);
  Serial.print(" display=");
  Serial.print(displayReady ? 1 : 0);
  Serial.print(" imu=");
  Serial.print(imuReady ? 1 : 0);
  Serial.print(" live=");
  Serial.print(liveMode ? 1 : 0);
  Serial.print(" inferences=");
  Serial.print(inferenceCount);
  Serial.print(" injected=");
  Serial.print(injectedCount);
  Serial.print(" label=");
  Serial.print(lastClassification.label);
  Serial.print(" confidence=");
  Serial.println(lastClassification.confidence, 3);
  Serial.flush();
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();
  if (command.length() == 0) {
    return;
  }
  if (command == "PING") {
    Serial.println("PONG");
    Serial.flush();
    return;
  }
  if (command == "MODEL?") {
    emitModel();
    return;
  }
  if (command == "STATUS?") {
    emitStatus();
    return;
  }
  if (command == "LIVE:1") {
    liveMode = true;
    Serial.println("TINYML_LIVE enabled=1");
    Serial.flush();
    return;
  }
  if (command == "LIVE:0") {
    liveMode = false;
    Serial.println("TINYML_LIVE enabled=0");
    Serial.flush();
    return;
  }
  if (command.startsWith("SAMPLE:")) {
    ImuSample injected;
    if (!parseSamplePayload(command.substring(7), injected)) {
      Serial.print("TINYML_BAD_SAMPLE value=");
      Serial.println(command.substring(7));
      Serial.flush();
      return;
    }
    liveMode = false;
    injectedCount++;
    runInference(injected, "serial");
    return;
  }

  Serial.print("TINYML_UNKNOWN_COMMAND value=");
  Serial.println(command);
  Serial.flush();
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    char ch = static_cast<char>(Serial.read());
    if (ch == '\r') {
      continue;
    }
    if (ch == '\n') {
      handleCommand(serialBuffer);
      serialBuffer = "";
      continue;
    }
    if (serialBuffer.length() < 120) {
      serialBuffer += ch;
    } else {
      serialBuffer = "";
      Serial.println("TINYML_COMMAND_TOO_LONG");
      Serial.flush();
    }
  }
}

void setup() {
  Serial.begin(115200);
  uint32_t serialWaitStart = millis();
  while (!Serial && (millis() - serialWaitStart < 5000)) {
    delay(100);
  }

  Serial.println("tinyml_imu_classifier boot");
  Serial.print("psram_kb=");
  Serial.println(ESP.getPsramSize() / 1024);
  Serial.flush();

  Wire.begin(IIC_SDA, IIC_SCL);
  setupDisplay();
  setupImu();
  emitModel();
  Serial.print((displayReady && imuReady) ? "TINYML_READY" : "TINYML_PARTIAL");
  Serial.print(" display=");
  Serial.print(displayReady ? 1 : 0);
  Serial.print(" imu=");
  Serial.println(imuReady ? 1 : 0);
  Serial.flush();
  emitStatus();
}

void loop() {
  readSerialCommands();
  updateLiveSample();

  if (liveMode && (frame % 10) == 0) {
    runInference(sample, "live");
  }
  if ((frame % 30) == 0) {
    emitStatus();
  }

  frame++;
  delay(100);
}
