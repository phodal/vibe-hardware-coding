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

READY_RE = re.compile(r"TINYML_(?:READY|PARTIAL) display=(?P<display>[01]) imu=(?P<imu>[01])")
CLASS_RE = re.compile(
    r"TINYML_CLASS source=(?P<source>\S+) label=(?P<label>\S+) confidence=(?P<confidence>\d+(?:\.\d+)?) "
    r"ax=(?P<ax>-?\d+(?:\.\d+)?) ay=(?P<ay>-?\d+(?:\.\d+)?) az=(?P<az>-?\d+(?:\.\d+)?) "
    r"gx=(?P<gx>-?\d+(?:\.\d+)?) gy=(?P<gy>-?\d+(?:\.\d+)?) gz=(?P<gz>-?\d+(?:\.\d+)?) "
    r"amag=(?P<amag>-?\d+(?:\.\d+)?) gmag=(?P<gmag>-?\d+(?:\.\d+)?)"
)
STATUS_RE = re.compile(
    r"TINYML_STATUS .*display=(?P<display>[01]) imu=(?P<imu>[01]) live=(?P<live>[01]) "
    r"inferences=(?P<inferences>\d+) injected=(?P<injected>\d+) label=(?P<label>\S+) "
    r"confidence=(?P<confidence>\d+(?:\.\d+)?)"
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

    def write_line(self, text: str) -> None:
        print(f"> {text}", flush=True)
        os.write(self.fd, (text + "\n").encode("utf-8"))

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

    def wait_for(self, predicate, timeout: float, label: str) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for line in self.read_lines(min(0.5, max(0.0, deadline - time.time()))):
                if predicate(line):
                    return line
        raise SystemExit(f"Timed out waiting for {label}")


def parse_classes(lines: list[str]) -> list[dict[str, str | float]]:
    classes = []
    for line in lines:
        match = CLASS_RE.search(line)
        if not match:
            continue
        item: dict[str, str | float] = {}
        for key, value in match.groupdict().items():
            if key in {"source", "label"}:
                item[key] = value
            else:
                item[key] = float(value)
        classes.append(item)
    return classes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the TinyML IMU classifier.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--allow-imu-missing", action="store_true")
    args = parser.parse_args()

    samples = [
        ("REST", "0.00,0.00,1.00,0.00,0.00,0.00"),
        ("TILT_LEFT", "-0.82,0.00,0.55,0.00,0.00,0.00"),
        ("TILT_RIGHT", "0.82,0.00,0.55,0.00,0.00,0.00"),
        ("SHAKE", "0.15,0.10,1.85,180.00,20.00,0.00"),
    ]

    collected: list[str] = []
    serial = SerialPort(args.port, args.baud)
    try:
        ready_line = serial.wait_for(
            lambda line: line.startswith("TINYML_READY")
            or line.startswith("TINYML_PARTIAL")
            or line.startswith("TINYML_STATUS"),
            15,
            "TINYML_READY",
        )
        collected.append(ready_line)
        ready = READY_RE.search(ready_line)
        status_ready = STATUS_RE.search(ready_line)
        if ready:
            if ready.group("display") != "1":
                raise SystemExit("TinyML display did not report ready.")
            if ready.group("imu") != "1" and not args.allow_imu_missing:
                raise SystemExit("TinyML IMU did not report ready.")
        elif status_ready:
            if status_ready.group("display") != "1":
                raise SystemExit("TinyML display did not report ready in status.")
            if status_ready.group("imu") != "1" and not args.allow_imu_missing:
                raise SystemExit("TinyML IMU did not report ready in status.")

        serial.write_line("PING")
        collected.append(serial.wait_for(lambda line: line == "PONG", 5, "PONG"))
        serial.write_line("MODEL?")
        collected.append(
            serial.wait_for(
                lambda line: line.startswith("TINYML_MODEL") and "classes=" in line,
                5,
                "TINYML_MODEL",
            )
        )
        serial.write_line("LIVE:0")
        collected.append(serial.wait_for(lambda line: line.startswith("TINYML_LIVE enabled=0"), 5, "TINYML_LIVE"))

        for expected_label, payload in samples:
            serial.write_line(f"SAMPLE:{payload}")
            collected.append(
                serial.wait_for(
                    lambda line, expected_label=expected_label: line.startswith("TINYML_CLASS")
                    and f"label={expected_label}" in line
                    and "source=serial" in line,
                    5,
                    f"TINYML_CLASS {expected_label}",
                )
            )

        serial.write_line("STATUS?")
        collected.append(serial.wait_for(lambda line: line.startswith("TINYML_STATUS"), 5, "TINYML_STATUS"))
        collected.extend(serial.read_lines(args.seconds))
    finally:
        serial.close()

    classes = parse_classes(collected)
    labels = [str(item["label"]) for item in classes if item["source"] == "serial"]
    required = {item[0] for item in samples}
    if not required.issubset(set(labels)):
        raise SystemExit(f"Missing expected labels {sorted(required - set(labels))}; saw {labels}")

    min_confidence = min(float(item["confidence"]) for item in classes if item["source"] == "serial")
    print(
        "tinyml_imu_summary "
        f"classifications={len(classes)} labels={','.join(labels)} "
        f"min_confidence={min_confidence:.3f}"
    )
    if min_confidence < 0.5:
        raise SystemExit(f"min_confidence {min_confidence:.3f} < 0.5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
