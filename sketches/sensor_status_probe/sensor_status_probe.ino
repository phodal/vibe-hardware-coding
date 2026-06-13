#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <SensorQMI8658.hpp>
#include <Wire.h>
#include <math.h>
#include "pin_config.h"
#include <XPowersLib.h>

#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 0
#endif

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
  LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);

Arduino_CO5300 *gfx = new Arduino_CO5300(
  bus, LCD_RESET, 0, LCD_WIDTH, LCD_HEIGHT, 6, 0, 0, 0);

XPowersPMU power;
SensorQMI8658 qmi;

bool displayReady = false;
bool pmuReady = false;
bool imuReady = false;
uint32_t frame = 0;
IMUdata acc = {0, 0, 0};
IMUdata gyr = {0, 0, 0};

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

void drawSensorScreen(uint16_t battMv, uint16_t vbusMv, float accMagnitude) {
  if (!displayReady) {
    return;
  }

  gfx->fillScreen(RGB565_BLACK);
  gfx->drawRect(8, 8, LCD_WIDTH - 16, LCD_HEIGHT - 16, RGB565_CYAN);
  centerText("SENS", 42, 6, RGB565_YELLOW);
  centerText((pmuReady && imuReady) ? "OK" : "WAIT", 130, 9, RGB565_WHITE);

  gfx->setTextSize(2);
  gfx->setTextColor(RGB565_GREEN, RGB565_BLACK);
  gfx->setCursor(54, 292);
  gfx->print("VBUS ");
  gfx->print(vbusMv);
  gfx->print("mV");

  gfx->setCursor(54, 326);
  gfx->print("BATT ");
  gfx->print(battMv);
  gfx->print("mV");

  gfx->setCursor(54, 360);
  gfx->print("ACC ");
  gfx->print(accMagnitude, 2);
  gfx->print("g");
}

void enablePmuAdc() {
  power.enableTemperatureMeasure();
  power.enableBattDetection();
  power.enableVbusVoltageMeasure();
  power.enableBattVoltageMeasure();
  power.enableSystemVoltageMeasure();
}

void setupDisplay() {
  if (!gfx->begin()) {
    Serial.println("sensor_status_probe gfx begin failed");
    Serial.flush();
    return;
  }

  gfx->setBrightness(200);
  gfx->setRotation(DISPLAY_ROTATION);
  displayReady = true;
  drawSensorScreen(0, 0, 0.0f);
}

void setupPmu() {
  pmuReady = power.begin(Wire, AXP2101_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!pmuReady) {
    Serial.println("SENSOR_PMU_FAILED");
    Serial.flush();
    return;
  }

  power.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
  power.clearIrqStatus();
  power.setChargeTargetVoltage(3);
  enablePmuAdc();
  Serial.println("SENSOR_PMU_READY");
  Serial.flush();
}

void setupImu() {
  imuReady = qmi.begin(Wire, QMI8658_L_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!imuReady) {
    Serial.println("SENSOR_IMU_FAILED");
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
  Serial.println("SENSOR_IMU_READY");
  Serial.flush();
}

void setup() {
  Serial.begin(115200);
  uint32_t serialWaitStart = millis();
  while (!Serial && (millis() - serialWaitStart < 5000)) {
    delay(100);
  }

  Serial.println("sensor_status_probe boot");
  Serial.print("psram_kb=");
  Serial.println(ESP.getPsramSize() / 1024);
  Serial.flush();

  Wire.begin(IIC_SDA, IIC_SCL);
  setupDisplay();
  setupPmu();
  setupImu();

  Serial.println((pmuReady && imuReady) ? "SENSOR_STATUS_READY" : "SENSOR_STATUS_PARTIAL");
  Serial.flush();
}

void loop() {
  if (imuReady && qmi.getDataReady()) {
    qmi.getAccelerometer(acc.x, acc.y, acc.z);
    qmi.getGyroscope(gyr.x, gyr.y, gyr.z);
  }

  uint16_t battMv = pmuReady ? power.getBattVoltage() : 0;
  uint16_t vbusMv = pmuReady ? power.getVbusVoltage() : 0;
  uint16_t systemMv = pmuReady ? power.getSystemVoltage() : 0;
  int batteryPercent = (pmuReady && power.isBatteryConnect()) ? power.getBatteryPercent() : -1;
  float temperature = pmuReady ? power.getTemperature() : 0.0f;
  float accMagnitude = sqrtf(acc.x * acc.x + acc.y * acc.y + acc.z * acc.z);

  if ((frame % 10) == 0) {
    Serial.print("SENSOR_PMU frame=");
    Serial.print(frame);
    Serial.print(" temp_c=");
    Serial.print(temperature, 2);
    Serial.print(" batt_mv=");
    Serial.print(battMv);
    Serial.print(" vbus_mv=");
    Serial.print(vbusMv);
    Serial.print(" system_mv=");
    Serial.print(systemMv);
    Serial.print(" battery_pct=");
    Serial.print(batteryPercent);
    Serial.print(" charging=");
    Serial.print(pmuReady && power.isCharging() ? 1 : 0);
    Serial.print(" vbus_in=");
    Serial.println(pmuReady && power.isVbusIn() ? 1 : 0);

    Serial.print("SENSOR_IMU frame=");
    Serial.print(frame);
    Serial.print(" ax=");
    Serial.print(acc.x, 3);
    Serial.print(" ay=");
    Serial.print(acc.y, 3);
    Serial.print(" az=");
    Serial.print(acc.z, 3);
    Serial.print(" amag=");
    Serial.print(accMagnitude, 3);
    Serial.print(" gx=");
    Serial.print(gyr.x, 3);
    Serial.print(" gy=");
    Serial.print(gyr.y, 3);
    Serial.print(" gz=");
    Serial.println(gyr.z, 3);
    Serial.flush();
  }

  if ((frame % 20) == 0) {
    drawSensorScreen(battMv, vbusMv, accMagnitude);
  }

  frame++;
  delay(100);
}
