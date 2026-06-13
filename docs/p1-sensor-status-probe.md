# P1 Sensor Status Probe

This slice validates two non-audio hardware surfaces:

- AXP2101 PMU: temperature, battery voltage, VBUS voltage, system voltage, charging state
- QMI8658 IMU: accelerometer and gyroscope metrics

The board displays `SENS OK` on the AMOLED and emits machine-readable serial metrics. The host checker validates PMU/IMU ranges without using the microphone or speaker, so this path is suitable for late-night validation.

## Commands

```bash
make sensor-status-build
make sensor-status-smoke
SENSOR_STATUS_VISUAL_SMOKE=1 DISPLAY_ROTATION=2 make sensor-status-smoke
```

## Acceptance Gates

- Compile: `make sensor-status-build`
- Serial:
  - `SENSOR_PMU_READY`
  - `SENSOR_IMU_READY`
  - repeated `SENSOR_PMU ...` metrics
  - repeated `SENSOR_IMU ...` metrics
- Host thresholds:
  - `SENSOR_MIN_SYSTEM_MV=2500`
  - `SENSOR_MIN_VBUS_MV=0`
  - `SENSOR_MIN_ACC_MAG=0.4`
  - `SENSOR_MAX_ACC_MAG=1.8`
- Visual: optional OCR sees `OK` on the AMOLED.

## Local Evidence

Last successful silent smoke:

```text
sensor_summary pmu_metrics=7 imu_metrics=7 max_system_mv=4311 max_vbus_mv=5171 max_batt_mv=4085 avg_acc_mag=0.978 max_abs_gyro=2.797
OCR validation passed.
```

Camera artifacts:

```text
/Users/phodal/hardware/arduino/.logs/camera-ocr-20260614-000008.jpg
/Users/phodal/hardware/arduino/.logs/camera-ocr-20260614-000008.processed.png
/Users/phodal/hardware/arduino/.logs/camera-ocr-20260614-000008.txt
```

Representative serial data:

```text
SENSOR_PMU frame=100 temp_c=42.40 batt_mv=4083 vbus_mv=5167 system_mv=4311 battery_pct=100 charging=0 vbus_in=1
SENSOR_IMU frame=100 ax=0.025 ay=0.034 az=0.978 amag=0.979 gx=1.219 gy=2.766 gz=-0.492
```

## Notes

- The PMU battery voltage can be `0` if no battery is connected, so the default hard gate uses system voltage rather than battery voltage.
- A stationary board should show accelerometer magnitude near 1 g. The default range allows desk angle and sensor noise but catches a dead IMU stream.
- This probe intentionally uses Arduino_GFX directly instead of LVGL. LVGL remains covered by official demo builds and can be promoted into a richer dashboard later.
