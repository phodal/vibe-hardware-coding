#!/usr/bin/env python3
import argparse
import os
import re
import select
import termios
import time


BAUDS = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: getattr(termios, "B230400", termios.B115200),
    460800: getattr(termios, "B460800", termios.B115200),
    921600: getattr(termios, "B921600", termios.B115200),
}

PMU_RE = re.compile(
    r"SENSOR_PMU .*temp_c=(?P<temp>-?\d+(?:\.\d+)?) "
    r"batt_mv=(?P<batt>\d+) vbus_mv=(?P<vbus>\d+) system_mv=(?P<system>\d+) "
    r"battery_pct=(?P<pct>-?\d+) charging=(?P<charging>[01]) vbus_in=(?P<vbus_in>[01])"
)
IMU_RE = re.compile(
    r"SENSOR_IMU .*ax=(?P<ax>-?\d+(?:\.\d+)?) ay=(?P<ay>-?\d+(?:\.\d+)?) "
    r"az=(?P<az>-?\d+(?:\.\d+)?) amag=(?P<amag>-?\d+(?:\.\d+)?) "
    r"gx=(?P<gx>-?\d+(?:\.\d+)?) gy=(?P<gy>-?\d+(?:\.\d+)?) gz=(?P<gz>-?\d+(?:\.\d+)?)"
)


class SerialPort:
    def __init__(self, path: str, baud: int) -> None:
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.buffer = b""
        self.configure(baud)

    def configure(self, baud: int) -> None:
        speed = BAUDS.get(baud)
        if speed is None:
            raise SystemExit(f"Unsupported baud: {baud}")
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def close(self) -> None:
        os.close(self.fd)

    def read_lines(self, timeout: float) -> list[str]:
        deadline = time.time() + timeout
        lines: list[str] = []
        while time.time() < deadline:
            readable, _, _ = select.select([self.fd], [], [], 0.1)
            if not readable:
                continue
            chunk = os.read(self.fd, 4096)
            if not chunk:
                continue
            self.buffer += chunk
            while b"\n" in self.buffer:
                raw, self.buffer = self.buffer.split(b"\n", 1)
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)
                    print(f"< {line}", flush=True)
        return lines

    def wait_for_any(self, needles: list[str], timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for line in self.read_lines(min(0.5, max(0.0, deadline - time.time()))):
                if any(needle in line for needle in needles):
                    return line
        raise SystemExit(f"Timed out waiting for any of {needles!r}")


def parse_metrics(lines: list[str]) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    pmu_metrics = []
    imu_metrics = []
    for line in lines:
        pmu = PMU_RE.search(line)
        if pmu:
            item = {key: float(value) for key, value in pmu.groupdict().items()}
            pmu_metrics.append(item)
            continue
        imu = IMU_RE.search(line)
        if imu:
            item = {key: float(value) for key, value in imu.groupdict().items()}
            imu_metrics.append(item)
    return pmu_metrics, imu_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AXP2101 PMU and QMI8658 IMU serial metrics.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--min-system-mv", type=float, default=2500.0)
    parser.add_argument("--min-vbus-mv", type=float, default=0.0)
    parser.add_argument("--min-acc-mag", type=float, default=0.4)
    parser.add_argument("--max-acc-mag", type=float, default=1.8)
    args = parser.parse_args()

    serial = SerialPort(args.port, args.baud)
    try:
        serial.wait_for_any(["SENSOR_STATUS_READY", "SENSOR_PMU", "SENSOR_IMU"], 15)
        lines = serial.read_lines(args.seconds)
    finally:
        serial.close()

    pmu_metrics, imu_metrics = parse_metrics(lines)
    if not pmu_metrics:
        raise SystemExit("No SENSOR_PMU metrics captured.")
    if not imu_metrics:
        raise SystemExit("No SENSOR_IMU metrics captured.")

    max_system = max(item["system"] for item in pmu_metrics)
    max_vbus = max(item["vbus"] for item in pmu_metrics)
    max_batt = max(item["batt"] for item in pmu_metrics)
    avg_acc_mag = sum(item["amag"] for item in imu_metrics) / len(imu_metrics)
    max_abs_gyro = max(
        max(abs(item["gx"]), abs(item["gy"]), abs(item["gz"]))
        for item in imu_metrics
    )

    print(
        "sensor_summary "
        f"pmu_metrics={len(pmu_metrics)} imu_metrics={len(imu_metrics)} "
        f"max_system_mv={max_system:.0f} max_vbus_mv={max_vbus:.0f} max_batt_mv={max_batt:.0f} "
        f"avg_acc_mag={avg_acc_mag:.3f} max_abs_gyro={max_abs_gyro:.3f}"
    )
    if max_system < args.min_system_mv:
        raise SystemExit(f"max_system_mv {max_system:.0f} < required {args.min_system_mv:.0f}")
    if max_vbus < args.min_vbus_mv:
        raise SystemExit(f"max_vbus_mv {max_vbus:.0f} < required {args.min_vbus_mv:.0f}")
    if not (args.min_acc_mag <= avg_acc_mag <= args.max_acc_mag):
        raise SystemExit(
            f"avg_acc_mag {avg_acc_mag:.3f} outside "
            f"[{args.min_acc_mag:.3f}, {args.max_acc_mag:.3f}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
