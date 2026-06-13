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

READY_RE = re.compile(
    r"DASH_(?:READY|PARTIAL) display=(?P<display>[01]) pmu=(?P<pmu>[01]) "
    r"imu=(?P<imu>[01]) touch=(?P<touch>[01])"
)
PAGE_RE = re.compile(r"DASH_PAGE page=(?P<page>\S+) source=(?P<source>\S+)")
STATUS_RE = re.compile(
    r"DASH_STATUS .*page=(?P<page>\S+) display=(?P<display>[01]) pmu=(?P<pmu>[01]) "
    r"imu=(?P<imu>[01]) touch=(?P<touch>[01]) events=(?P<events>\d+) "
    r"system_mv=(?P<system>\d+) vbus_mv=(?P<vbus>\d+) batt_mv=(?P<batt>\d+) "
    r"amag=(?P<amag>-?\d+(?:\.\d+)?) gx=(?P<gx>-?\d+(?:\.\d+)?) "
    r"gy=(?P<gy>-?\d+(?:\.\d+)?) gz=(?P<gz>-?\d+(?:\.\d+)?)"
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


def parse_status(lines: list[str]) -> list[dict[str, float | str]]:
    statuses: list[dict[str, float | str]] = []
    for line in lines:
        match = STATUS_RE.search(line)
        if not match:
            continue
        item: dict[str, float | str] = {}
        for key, value in match.groupdict().items():
            if key == "page":
                item[key] = value
            else:
                item[key] = float(value)
        statuses.append(item)
    return statuses


def parse_page_flow(lines: list[str]) -> list[str]:
    flow = []
    for line in lines:
        match = PAGE_RE.search(line)
        if match and match.group("source") == "serial":
            flow.append(match.group("page"))
    return flow


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the non-audio interaction dashboard.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--pages", default="IMU,PWR,TOUCH,HOME")
    parser.add_argument("--min-system-mv", type=float, default=2500.0)
    parser.add_argument("--min-acc-mag", type=float, default=0.4)
    parser.add_argument("--max-acc-mag", type=float, default=1.8)
    parser.add_argument("--allow-touch-missing", action="store_true")
    args = parser.parse_args()

    pages = [item.strip().upper() for item in args.pages.split(",") if item.strip()]
    serial = SerialPort(args.port, args.baud)
    collected: list[str] = []
    try:
        ready_line = serial.wait_for(
            lambda line: line.startswith("DASH_READY")
            or line.startswith("DASH_PARTIAL")
            or line.startswith("DASH_STATUS"),
            15,
            "DASH_READY or DASH_STATUS",
        )
        collected.append(ready_line)
        ready = READY_RE.search(ready_line)
        status_ready = STATUS_RE.search(ready_line)
        if not ready and not status_ready:
            raise SystemExit(f"Could not parse ready line: {ready_line}")
        ready_values = (ready or status_ready).groupdict()
        for key in ("display", "pmu", "imu"):
            if ready_values[key] != "1":
                raise SystemExit(f"Dashboard reported {key}=0 in ready line.")
        if ready_values["touch"] != "1" and not args.allow_touch_missing:
            raise SystemExit("Dashboard reported touch=0 in ready line.")

        serial.write_line("PING")
        collected.append(serial.wait_for(lambda line: line == "PONG", 5, "PONG"))

        for page in pages:
            serial.write_line(f"PAGE:{page}")
            expected = f"page={page}"
            collected.append(
                serial.wait_for(
                    lambda line, expected=expected: line.startswith("DASH_PAGE")
                    and expected in line
                    and "source=serial" in line,
                    5,
                    f"DASH_PAGE {page}",
                )
            )

        collected.extend(serial.read_lines(args.seconds))
    finally:
        serial.close()

    statuses = parse_status(collected)
    if not statuses:
        raise SystemExit("No DASH_STATUS metrics captured.")
    page_flow = parse_page_flow(collected)

    max_system = max(float(item["system"]) for item in statuses)
    avg_acc_mag = sum(float(item["amag"]) for item in statuses) / len(statuses)
    seen_pages = sorted({str(item["page"]) for item in statuses})

    print(
        "interaction_dashboard_summary "
        f"statuses={len(statuses)} pages={','.join(seen_pages)} "
        f"page_flow={','.join(page_flow)} "
        f"max_system_mv={max_system:.0f} avg_acc_mag={avg_acc_mag:.3f}"
    )

    if max_system < args.min_system_mv:
        raise SystemExit(f"max_system_mv {max_system:.0f} < required {args.min_system_mv:.0f}")
    if not (args.min_acc_mag <= avg_acc_mag <= args.max_acc_mag):
        raise SystemExit(
            f"avg_acc_mag {avg_acc_mag:.3f} outside "
            f"[{args.min_acc_mag:.3f}, {args.max_acc_mag:.3f}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
