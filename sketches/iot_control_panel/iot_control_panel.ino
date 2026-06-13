#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <TouchDrvCSTXXX.hpp>
#include <Wire.h>
#include "pin_config.h"

#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 0
#endif

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
  LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);

Arduino_CO5300 *gfx = new Arduino_CO5300(
  bus, LCD_RESET, 0, LCD_WIDTH, LCD_HEIGHT, 6, 0, 0, 0);

TouchDrvCST92xx touch;

enum PanelPage {
  PANEL_HOME = 0,
  PANEL_DEVICES,
  PANEL_SCENE,
  PANEL_LOG,
};

struct DeviceState {
  char name[24];
  char kind[12];
  char state[12];
  int value;
  bool online;
};

DeviceState devices[] = {
  {"Light", "light", "OFF", 0, true},
  {"Fan", "switch", "OFF", 0, true},
  {"Door", "lock", "CLOSED", 0, true},
  {"Climate", "climate", "ON", 24, true},
};
constexpr uint8_t DEVICE_COUNT = sizeof(devices) / sizeof(devices[0]);

bool displayReady = false;
bool touchReady = false;
uint32_t frame = 0;
uint32_t touchEvents = 0;
uint32_t commandCount = 0;
uint32_t toggleCount = 0;
uint32_t haCount = 0;
uint32_t mqttCount = 0;
uint32_t httpCount = 0;
uint8_t selectedDevice = 0;
PanelPage currentPage = PANEL_HOME;
String serialBuffer;
int16_t touchX[5] = {0};
int16_t touchY[5] = {0};
char activeScene[16] = "HOME";
char lastAction[72] = "Ready";
char lastTopic[48] = "-";
char lastHttp[48] = "-";

const char *pageName(PanelPage page) {
  switch (page) {
    case PANEL_HOME:
      return "HOME";
    case PANEL_DEVICES:
      return "DEVICES";
    case PANEL_SCENE:
      return "SCENE";
    case PANEL_LOG:
      return "LOG";
  }
  return "HOME";
}

bool parsePage(const String &name, PanelPage &page) {
  if (name == "HOME" || name == "IOT") {
    page = PANEL_HOME;
    return true;
  }
  if (name == "DEVICES" || name == "DEVICE") {
    page = PANEL_DEVICES;
    return true;
  }
  if (name == "SCENE" || name == "SCENES") {
    page = PANEL_SCENE;
    return true;
  }
  if (name == "LOG") {
    page = PANEL_LOG;
    return true;
  }
  return false;
}

uint16_t stateColor(const char *state) {
  if (strcmp(state, "ON") == 0 || strcmp(state, "OPEN") == 0) {
    return RGB565_GREEN;
  }
  if (strcmp(state, "WARN") == 0 || strcmp(state, "UNKNOWN") == 0) {
    return RGB565_YELLOW;
  }
  return RGB565_CYAN;
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

void drawLine(const char *label, int16_t y, uint16_t color) {
  gfx->setTextSize(2);
  gfx->setTextColor(color, RGB565_BLACK);
  gfx->setCursor(42, y);
  gfx->print(label);
}

void drawFrame(uint16_t color) {
  gfx->fillScreen(RGB565_BLACK);
  gfx->drawRect(8, 8, LCD_WIDTH - 16, LCD_HEIGHT - 16, color);
}

uint8_t onlineCount() {
  uint8_t count = 0;
  for (uint8_t i = 0; i < DEVICE_COUNT; i++) {
    if (devices[i].online) {
      count++;
    }
  }
  return count;
}

uint8_t activeCount() {
  uint8_t count = 0;
  for (uint8_t i = 0; i < DEVICE_COUNT; i++) {
    if (strcmp(devices[i].state, "ON") == 0 || strcmp(devices[i].state, "OPEN") == 0) {
      count++;
    }
  }
  return count;
}

void drawDeviceRow(uint8_t index, int16_t y) {
  DeviceState &device = devices[index];
  uint16_t color = index == selectedDevice ? RGB565_YELLOW : stateColor(device.state);
  gfx->setTextSize(2);
  gfx->setTextColor(color, RGB565_BLACK);
  gfx->setCursor(42, y);
  gfx->print(index == selectedDevice ? ">" : " ");
  gfx->print(device.name);
  gfx->print(" ");
  gfx->print(device.state);
  if (strcmp(device.kind, "climate") == 0) {
    gfx->print(" ");
    gfx->print(device.value);
    gfx->print("C");
  }
}

void drawPage() {
  if (!displayReady) {
    return;
  }

  switch (currentPage) {
    case PANEL_HOME:
      drawFrame(RGB565_CYAN);
      centerText("IOT", 44, 7, RGB565_CYAN);
      centerText("OK", 132, 9, RGB565_WHITE);
      drawLine("scene=", 292, RGB565_GREEN);
      gfx->print(activeScene);
      drawLine("active=", 330, RGB565_GREEN);
      gfx->print(activeCount());
      drawLine("online=", 368, RGB565_GREEN);
      gfx->print(onlineCount());
      break;
    case PANEL_DEVICES:
      drawFrame(RGB565_GREEN);
      centerText("DEVICES", 42, 5, RGB565_CYAN);
      for (uint8_t i = 0; i < DEVICE_COUNT; i++) {
        drawDeviceRow(i, 146 + i * 46);
      }
      break;
    case PANEL_SCENE:
      drawFrame(RGB565_YELLOW);
      centerText("SCENE", 44, 6, RGB565_CYAN);
      centerText(activeScene, 132, 6, RGB565_WHITE);
      drawLine("HOME AWAY NIGHT", 300, RGB565_GREEN);
      drawLine("Use SCENE:name", 338, RGB565_GREEN);
      break;
    case PANEL_LOG:
      drawFrame(RGB565_CYAN);
      centerText("LOG", 44, 7, RGB565_CYAN);
      drawLine(lastAction, 150, RGB565_WHITE);
      drawLine(lastTopic, 210, RGB565_GREEN);
      drawLine(lastHttp, 270, RGB565_YELLOW);
      break;
  }
}

void emitPage(const char *source) {
  Serial.print("IOT_PAGE page=");
  Serial.print(pageName(currentPage));
  Serial.print(" source=");
  Serial.println(source);
  Serial.flush();
}

void setPage(PanelPage page, const char *source) {
  currentPage = page;
  drawPage();
  emitPage(source);
}

void copyString(char *target, size_t targetSize, const String &value) {
  String sanitized = value;
  sanitized.replace("\r", " ");
  sanitized.replace("\n", " ");
  sanitized.trim();
  strlcpy(target, sanitized.c_str(), targetSize);
}

void emitState() {
  Serial.print("IOT_STATE frame=");
  Serial.print(frame);
  Serial.print(" page=");
  Serial.print(pageName(currentPage));
  Serial.print(" display=");
  Serial.print(displayReady ? 1 : 0);
  Serial.print(" touch=");
  Serial.print(touchReady ? 1 : 0);
  Serial.print(" selected=");
  Serial.print(selectedDevice);
  Serial.print(" devices=");
  Serial.print(DEVICE_COUNT);
  Serial.print(" online=");
  Serial.print(onlineCount());
  Serial.print(" active=");
  Serial.print(activeCount());
  Serial.print(" scene=");
  Serial.print(activeScene);
  Serial.print(" toggles=");
  Serial.print(toggleCount);
  Serial.print(" ha=");
  Serial.print(haCount);
  Serial.print(" mqtt=");
  Serial.print(mqttCount);
  Serial.print(" http=");
  Serial.print(httpCount);
  Serial.print(" commands=");
  Serial.println(commandCount);
  Serial.flush();
}

void emitDevice(uint8_t index, const char *source) {
  DeviceState &device = devices[index];
  Serial.print("IOT_DEVICE idx=");
  Serial.print(index);
  Serial.print(" name=");
  Serial.print(device.name);
  Serial.print(" kind=");
  Serial.print(device.kind);
  Serial.print(" state=");
  Serial.print(device.state);
  Serial.print(" value=");
  Serial.print(device.value);
  Serial.print(" online=");
  Serial.print(device.online ? 1 : 0);
  Serial.print(" source=");
  Serial.println(source);
  Serial.flush();
}

void emitHomeAssistant(const String &service, uint8_t index, const char *action) {
  Serial.print("IOT_HA service=");
  Serial.print(service);
  Serial.print(" idx=");
  Serial.print(index);
  Serial.print(" action=");
  Serial.print(action);
  Serial.print(" state=");
  Serial.print(devices[index].state);
  Serial.print(" value=");
  Serial.println(devices[index].value);
  Serial.flush();
}

bool validIndex(long index) {
  return index >= 0 && index < DEVICE_COUNT;
}

void setDeviceState(uint8_t index, const String &state, const char *source) {
  String upper = state;
  upper.toUpperCase();
  copyString(devices[index].state, sizeof(devices[index].state), upper);
  devices[index].online = true;
  selectedDevice = index;
  snprintf(lastAction, sizeof(lastAction), "%s=%s", devices[index].name, devices[index].state);
  drawPage();
  emitDevice(index, source);
}

void toggleDevice(uint8_t index, const char *source) {
  if (strcmp(devices[index].state, "ON") == 0 || strcmp(devices[index].state, "OPEN") == 0) {
    setDeviceState(index, strcmp(devices[index].kind, "lock") == 0 ? "CLOSED" : "OFF", source);
  } else {
    setDeviceState(index, strcmp(devices[index].kind, "lock") == 0 ? "OPEN" : "ON", source);
  }
  toggleCount++;
}

void setScene(const String &scene, const char *source) {
  String upper = scene;
  upper.toUpperCase();
  copyString(activeScene, sizeof(activeScene), upper);
  if (upper == "NIGHT") {
    setDeviceState(0, "OFF", source);
    setDeviceState(1, "OFF", source);
  } else if (upper == "AWAY") {
    setDeviceState(0, "OFF", source);
    setDeviceState(1, "OFF", source);
    setDeviceState(2, "CLOSED", source);
  } else {
    setDeviceState(0, "ON", source);
  }
  snprintf(lastAction, sizeof(lastAction), "scene=%s", activeScene);
  setPage(PANEL_SCENE, source);
}

void handleHomeAssistant(const String &payload) {
  int firstColon = payload.indexOf(':');
  int secondColon = firstColon > 0 ? payload.indexOf(':', firstColon + 1) : -1;
  if (firstColon <= 0 || secondColon <= 0) {
    Serial.print("IOT_HA_BAD value=");
    Serial.println(payload);
    Serial.flush();
    return;
  }

  String service = payload.substring(0, firstColon);
  String serviceUpper = service;
  serviceUpper.toUpperCase();
  long index = payload.substring(firstColon + 1, secondColon).toInt();
  if (!validIndex(index)) {
    Serial.print("IOT_HA_BAD_INDEX value=");
    Serial.println(index);
    Serial.flush();
    return;
  }

  String value = payload.substring(secondColon + 1);
  value.trim();
  String upperValue = value;
  upperValue.toUpperCase();

  uint8_t deviceIndex = static_cast<uint8_t>(index);
  const char *action = "SET";
  haCount++;
  if (serviceUpper.endsWith(".TOGGLE") || upperValue == "TOGGLE") {
    action = "TOGGLE";
    toggleDevice(deviceIndex, "ha");
  } else if (serviceUpper.endsWith(".SET_TEMPERATURE") || serviceUpper.endsWith(".SET_VALUE")) {
    action = "VALUE";
    devices[deviceIndex].value = value.toInt();
    devices[deviceIndex].online = true;
    selectedDevice = deviceIndex;
    snprintf(lastAction, sizeof(lastAction), "ha value %s", devices[deviceIndex].name);
    drawPage();
    emitDevice(deviceIndex, "ha");
  } else if (serviceUpper.endsWith(".TURN_OFF")) {
    action = "OFF";
    setDeviceState(deviceIndex, "OFF", "ha");
  } else if (serviceUpper.endsWith(".LOCK")) {
    action = "LOCK";
    setDeviceState(deviceIndex, "CLOSED", "ha");
  } else if (serviceUpper.endsWith(".UNLOCK") || serviceUpper.endsWith(".OPEN")) {
    action = "OPEN";
    setDeviceState(deviceIndex, "OPEN", "ha");
  } else {
    if (value.length() == 0 || upperValue == "ON") {
      action = "ON";
      setDeviceState(deviceIndex, "ON", "ha");
    } else {
      setDeviceState(deviceIndex, value, "ha");
    }
  }

  snprintf(lastAction, sizeof(lastAction), "ha %s", service.c_str());
  emitHomeAssistant(service, deviceIndex, action);
  setPage(PANEL_LOG, "ha");
}

void resetTouchPins() {
  pinMode(TP_RST, OUTPUT);
  digitalWrite(TP_RST, LOW);
  delay(30);
  digitalWrite(TP_RST, HIGH);
  delay(150);
}

void setupDisplay() {
  if (!gfx->begin()) {
    Serial.println("IOT_DISPLAY_FAILED");
    Serial.flush();
    return;
  }

  gfx->setRotation(DISPLAY_ROTATION);
  gfx->setBrightness(190);
  displayReady = true;
  drawPage();
}

void setupTouch() {
  resetTouchPins();
  touch.setPins(TP_RST, TP_INT);
  touchReady = touch.begin(Wire, CST92XX_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!touchReady) {
    Serial.println("IOT_TOUCH_FAILED");
    Serial.flush();
    return;
  }

  touch.reset();
  touch.setMaxCoordinates(LCD_WIDTH, LCD_HEIGHT);
  touch.setMirrorXY(true, true);
  Serial.print("IOT_TOUCH_READY model=");
  Serial.print(touch.getModelName());
  Serial.print(" points=");
  Serial.println(touch.getSupportTouchPoint());
  Serial.flush();
}

void handleTouch() {
  if (!touchReady) {
    return;
  }

  uint8_t touched = touch.getPoint(touchX, touchY, touch.getSupportTouchPoint());
  if (touched == 0) {
    return;
  }

  touchEvents++;
  selectedDevice = (selectedDevice + 1) % DEVICE_COUNT;
  Serial.print("IOT_TOUCH_EVENT count=");
  Serial.print(touchEvents);
  Serial.print(" selected=");
  Serial.print(selectedDevice);
  Serial.print(" x=");
  Serial.print(touchX[0]);
  Serial.print(" y=");
  Serial.println(touchY[0]);
  Serial.flush();
  setPage(PANEL_DEVICES, "touch");
  delay(220);
}

void handleCommand(String command) {
  command.trim();
  if (command.length() == 0) {
    return;
  }
  commandCount++;

  String upper = command;
  upper.toUpperCase();
  if (upper == "PING") {
    Serial.println("PONG");
    Serial.flush();
    return;
  }
  if (upper == "STATE?") {
    emitState();
    return;
  }
  if (upper == "NEXT") {
    setPage(static_cast<PanelPage>((currentPage + 1) % 4), "serial");
    return;
  }
  if (upper.startsWith("PAGE:")) {
    PanelPage page;
    if (parsePage(upper.substring(5), page)) {
      setPage(page, "serial");
    } else {
      Serial.print("IOT_BAD_PAGE value=");
      Serial.println(upper.substring(5));
      Serial.flush();
    }
    return;
  }
  if (upper.startsWith("IOT:SELECT:")) {
    long index = command.substring(11).toInt();
    if (validIndex(index)) {
      selectedDevice = static_cast<uint8_t>(index);
      setPage(PANEL_DEVICES, "serial");
      emitDevice(selectedDevice, "serial");
    }
    return;
  }
  if (upper.startsWith("IOT:TOGGLE:")) {
    long index = command.substring(11).toInt();
    if (validIndex(index)) {
      toggleDevice(static_cast<uint8_t>(index), "serial");
      setPage(PANEL_DEVICES, "serial");
    }
    return;
  }
  if (upper.startsWith("IOT:SET:")) {
    int stateIndex = command.indexOf(':', 8);
    if (stateIndex > 0) {
      long index = command.substring(8, stateIndex).toInt();
      if (validIndex(index)) {
        setDeviceState(static_cast<uint8_t>(index), command.substring(stateIndex + 1), "serial");
        setPage(PANEL_DEVICES, "serial");
      }
    }
    return;
  }
  if (upper.startsWith("IOT:VALUE:")) {
    int valueIndex = command.indexOf(':', 10);
    if (valueIndex > 0) {
      long index = command.substring(10, valueIndex).toInt();
      if (validIndex(index)) {
        devices[index].value = command.substring(valueIndex + 1).toInt();
        selectedDevice = static_cast<uint8_t>(index);
        snprintf(lastAction, sizeof(lastAction), "%s value=%d", devices[index].name, devices[index].value);
        drawPage();
        emitDevice(selectedDevice, "serial");
      }
    }
    return;
  }
  if (upper.startsWith("IOT:HA:")) {
    handleHomeAssistant(command.substring(7));
    return;
  }
  if (upper.startsWith("IOT:MQTT:")) {
    int topicEnd = command.indexOf(':', 9);
    int indexEnd = topicEnd > 0 ? command.indexOf(':', topicEnd + 1) : -1;
    if (topicEnd > 0 && indexEnd > 0) {
      copyString(lastTopic, sizeof(lastTopic), command.substring(9, topicEnd));
      long index = command.substring(topicEnd + 1, indexEnd).toInt();
      if (validIndex(index)) {
        mqttCount++;
        setDeviceState(static_cast<uint8_t>(index), command.substring(indexEnd + 1), "mqtt");
        Serial.print("IOT_MQTT topic=");
        Serial.print(lastTopic);
        Serial.print(" idx=");
        Serial.print(index);
        Serial.print(" state=");
        Serial.println(devices[index].state);
        Serial.flush();
        setPage(PANEL_LOG, "serial");
      }
    }
    return;
  }
  if (upper.startsWith("IOT:HTTP:")) {
    int pathIndex = command.indexOf(':', 9);
    int statusIndex = pathIndex > 0 ? command.indexOf(':', pathIndex + 1) : -1;
    if (pathIndex > 0 && statusIndex > 0) {
      httpCount++;
      String method = upper.substring(9, pathIndex);
      String path = command.substring(pathIndex + 1, statusIndex);
      String status = command.substring(statusIndex + 1);
      snprintf(lastHttp, sizeof(lastHttp), "%s %s", method.c_str(), status.c_str());
      snprintf(lastAction, sizeof(lastAction), "http %s", path.c_str());
      Serial.print("IOT_HTTP method=");
      Serial.print(method);
      Serial.print(" path=");
      Serial.print(path);
      Serial.print(" status=");
      Serial.println(status);
      Serial.flush();
      setPage(PANEL_LOG, "serial");
    }
    return;
  }
  if (upper.startsWith("SCENE:")) {
    setScene(command.substring(6), "serial");
    return;
  }

  Serial.print("IOT_UNKNOWN_COMMAND value=");
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
    if (serialBuffer.length() < 160) {
      serialBuffer += ch;
    } else {
      serialBuffer = "";
      Serial.println("IOT_COMMAND_TOO_LONG");
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

  Serial.println("iot_control_panel boot");
  Serial.print("psram_kb=");
  Serial.println(ESP.getPsramSize() / 1024);
  Serial.flush();

  Wire.begin(IIC_SDA, IIC_SCL);
  setupDisplay();
  setupTouch();

  Serial.print((displayReady && touchReady) ? "IOT_READY" : "IOT_PARTIAL");
  Serial.print(" display=");
  Serial.print(displayReady ? 1 : 0);
  Serial.print(" touch=");
  Serial.print(touchReady ? 1 : 0);
  Serial.print(" devices=");
  Serial.println(DEVICE_COUNT);
  Serial.flush();
  emitPage("boot");
  emitState();
}

void loop() {
  readSerialCommands();
  handleTouch();

  if ((frame % 20) == 0) {
    emitState();
    drawPage();
  }

  frame++;
  delay(50);
}
