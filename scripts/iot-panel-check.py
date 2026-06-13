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

READY_RE = re.compile(r"IOT_(?:READY|PARTIAL) display=(?P<display>[01]) touch=(?P<touch>[01]) devices=(?P<devices>\d+)")
PAGE_RE = re.compile(r"IOT_PAGE page=(?P<page>\S+) source=(?P<source>\S+)")
STATE_RE = re.compile(
    r"IOT_STATE .*page=(?P<page>\S+) display=(?P<display>[01]) touch=(?P<touch>[01]) "
    r"selected=(?P<selected>\d+) devices=(?P<devices>\d+) online=(?P<online>\d+) "
    r"active=(?P<active>\d+) scene=(?P<scene>\S+) toggles=(?P<toggles>\d+) "
    r"ha=(?P<ha>\d+) mqtt=(?P<mqtt>\d+) http=(?P<http>\d+) commands=(?P<commands>\d+)"
)
DEVICE_RE = re.compile(
    r"IOT_DEVICE idx=(?P<idx>\d+) name=(?P<name>\S+) kind=(?P<kind>\S+) "
    r"state=(?P<state>\S+) value=(?P<value>-?\d+) online=(?P<online>[01]) source=(?P<source>\S+)"
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


def parse_states(lines: list[str]) -> list[dict[str, str | int]]:
    states = []
    for line in lines:
        match = STATE_RE.search(line)
        if not match:
            continue
        item: dict[str, str | int] = {}
        for key, value in match.groupdict().items():
            if key in {"page", "scene"}:
                item[key] = value
            else:
                item[key] = int(value)
        states.append(item)
    return states


def parse_pages(lines: list[str]) -> list[str]:
    pages = []
    for line in lines:
        match = PAGE_RE.search(line)
        if match and match.group("source") == "serial":
            pages.append(match.group("page"))
    return pages


def parse_devices(lines: list[str]) -> list[dict[str, str | int]]:
    devices = []
    for line in lines:
        match = DEVICE_RE.search(line)
        if not match:
            continue
        item: dict[str, str | int] = {}
        for key, value in match.groupdict().items():
            if key in {"idx", "value", "online"}:
                item[key] = int(value)
            else:
                item[key] = value
        devices.append(item)
    return devices


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the serial-driven IoT control panel.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--allow-touch-missing", action="store_true")
    args = parser.parse_args()

    collected: list[str] = []
    serial = SerialPort(args.port, args.baud)
    try:
        ready_line = serial.wait_for(
            lambda line: line.startswith("IOT_READY")
            or line.startswith("IOT_PARTIAL")
            or line.startswith("IOT_STATE"),
            15,
            "IOT_READY",
        )
        collected.append(ready_line)
        ready = READY_RE.search(ready_line)
        state_ready = STATE_RE.search(ready_line)
        if ready:
            if ready.group("display") != "1":
                raise SystemExit("IoT panel display did not report ready.")
            if ready.group("touch") != "1" and not args.allow_touch_missing:
                raise SystemExit("IoT panel touch did not report ready.")
            if int(ready.group("devices")) < 4:
                raise SystemExit("IoT panel reported too few devices.")
        elif state_ready:
            if state_ready.group("display") != "1":
                raise SystemExit("IoT panel display did not report ready in state.")
            if state_ready.group("touch") != "1" and not args.allow_touch_missing:
                raise SystemExit("IoT panel touch did not report ready in state.")
        else:
            raise SystemExit(f"Could not parse ready line: {ready_line}")

        serial.write_line("PING")
        collected.append(serial.wait_for(lambda line: line == "PONG", 5, "PONG"))

        commands = [
            ("PAGE:DEVICES", "IOT_PAGE", "page=DEVICES"),
            ("IOT:SET:0:ON", "IOT_DEVICE", "idx=0"),
            ("IOT:TOGGLE:1", "IOT_DEVICE", "idx=1"),
            ("IOT:HA:light.turn_on:0:ON", "IOT_HA", "service=light.turn_on"),
            ("IOT:HA:switch.toggle:1:TOGGLE", "IOT_HA", "action=TOGGLE"),
            ("IOT:MQTT:home/door:2:OPEN", "IOT_MQTT", "idx=2"),
            ("IOT:HTTP:POST:/api/light/turn_on:200", "IOT_HTTP", "status=200"),
            ("SCENE:NIGHT", "IOT_PAGE", "page=SCENE"),
            ("PAGE:LOG", "IOT_PAGE", "page=LOG"),
            ("PAGE:HOME", "IOT_PAGE", "page=HOME"),
        ]
        for command, prefix, needle in commands:
            serial.write_line(command)
            collected.append(
                serial.wait_for(
                    lambda line, prefix=prefix, needle=needle: line.startswith(prefix)
                    and needle in line,
                    5,
                    f"{prefix} {needle}",
                )
            )

        serial.write_line("STATE?")
        collected.append(serial.wait_for(lambda line: line.startswith("IOT_STATE"), 5, "IOT_STATE"))
        collected.extend(serial.read_lines(args.seconds))
    finally:
        serial.close()

    states = parse_states(collected)
    if not states:
        raise SystemExit("No IOT_STATE lines captured.")
    latest = states[-1]
    pages = parse_pages(collected)
    devices = parse_devices(collected)
    mqtt_events = [line for line in collected if line.startswith("IOT_MQTT") and "idx=2" in line and "state=OPEN" in line]

    if int(latest["devices"]) < 4:
        raise SystemExit(f"Expected at least 4 devices, saw {latest['devices']}")
    if int(latest["online"]) < 4:
        raise SystemExit(f"Expected all devices online, saw {latest['online']}")
    if int(latest["ha"]) < 2:
        raise SystemExit("Expected at least two Home Assistant service events.")
    if int(latest["mqtt"]) < 1:
        raise SystemExit("Expected at least one MQTT event.")
    if int(latest["http"]) < 1:
        raise SystemExit("Expected at least one HTTP event.")
    if latest["scene"] != "NIGHT":
        raise SystemExit(f"Expected scene=NIGHT, saw {latest['scene']}")
    if not mqtt_events and not any(item["idx"] == 2 and item["state"] == "OPEN" and item["source"] == "mqtt" for item in devices):
        raise SystemExit("Expected MQTT device update for idx=2 OPEN.")
    if not {"DEVICES", "SCENE", "LOG", "HOME"}.issubset(set(pages)):
        raise SystemExit(f"Missing expected page flow, saw {pages}")

    print(
        "iot_panel_summary "
        f"states={len(states)} page_flow={','.join(pages)} "
        f"devices={latest['devices']} online={latest['online']} active={latest['active']} "
        f"scene={latest['scene']} toggles={latest['toggles']} ha={latest['ha']} "
        f"mqtt={latest['mqtt']} http={latest['http']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
