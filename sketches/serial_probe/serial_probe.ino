#include <Arduino.h>

uint32_t frame = 0;

void setup() {
  Serial.begin(115200);
  uint32_t start = millis();
  while (!Serial && (millis() - start < 8000)) {
    delay(100);
  }
  Serial.println("serial_probe boot");
  Serial.flush();
}

void loop() {
  Serial.print("serial_probe frame=");
  Serial.println(frame++);
  Serial.flush();
  delay(500);
}

