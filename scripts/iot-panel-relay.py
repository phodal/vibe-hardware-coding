#!/usr/bin/env python3
import argparse
import json
import os
import re
import select
import termios
import time
import urllib.request
from pathlib import Path
from typing import Any


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

STATE_RE = re.compile(
    r"IOT_STATE .*devices=(?P<devices>\d+) online=(?P<online>\d+) "
    r"active=(?P<active>\d+) scene=(?P<scene>\S+) toggles=(?P<toggles>\d+) "
    r"mqtt=(?P<mqtt>\d+) http=(?P<http>\d+) commands=(?P<commands>\d+)"
)


MOCK_EVENTS: dict[str, Any] = {
    "home_assistant": [
        {"service": "light.turn_on", "index": 0, "state": "ON"},
        {"service": "switch.toggle", "index": 1, "toggle": True},
        {"service": "climate.set_temperature", "index": 3, "value": 23},
    ],
    "mqtt": [{"topic": "home/door", "index": 2, "state": "OPEN"}],
    "http": [{"method": "POST", "path": "/api/light/turn_on", "status": 200}],
    "scene": "NIGHT",
}


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

    def write_line(self, line: str) -> None:
        print(f"> {line}", flush=True)
        os.write(self.fd, (line.rstrip("\n") + "\n").encode("utf-8"))

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

    def wait_for(self, needle: str, timeout: float) -> str:
        deadline = time.time() + timeout
        seen: list[str] = []
        while time.time() < deadline:
            for line in self.read_lines(min(0.5, max(0.0, deadline - time.time()))):
                seen.append(line)
                if needle in line:
                    return line
        raise SystemExit(f"Timed out waiting for {needle!r}. Last lines: {seen[-8:]}")


def load_events(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "mock":
        return dict(MOCK_EVENTS)
    if args.mode == "json":
        if not args.events_json:
            raise SystemExit("--events-json is required for mode=json")
        data = json.loads(Path(args.events_json).read_text(encoding="utf-8"))
    else:
        if not args.endpoint:
            raise SystemExit("--endpoint is required for mode=http")
        with urllib.request.urlopen(args.endpoint, timeout=args.timeout) as response:
            data = json.load(response)
    if not isinstance(data, dict):
        raise SystemExit("Events payload must be a JSON object")
    return data


def send_and_wait(serial: SerialPort, command: str, needle: str) -> str:
    serial.write_line(command)
    return serial.wait_for(needle, 5)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def apply_home_assistant(serial: SerialPort, events: dict[str, Any]) -> int:
    count = 0
    for item in as_list(events.get("home_assistant")):
        if not isinstance(item, dict):
            continue
        index = int(item.get("index", 0))
        if item.get("toggle", False):
            send_and_wait(serial, f"IOT:TOGGLE:{index}", f"IOT_DEVICE idx={index}")
            count += 1
            continue
        if "value" in item:
            send_and_wait(serial, f"IOT:VALUE:{index}:{int(item['value'])}", f"IOT_DEVICE idx={index}")
            count += 1
            continue
        state = str(item.get("state", "ON")).upper()
        send_and_wait(serial, f"IOT:SET:{index}:{state}", f"IOT_DEVICE idx={index}")
        count += 1
    return count


def apply_mqtt(serial: SerialPort, events: dict[str, Any]) -> int:
    count = 0
    for item in as_list(events.get("mqtt")):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "home/device"))[:32]
        index = int(item.get("index", 0))
        state = str(item.get("state", "ON")).upper()
        send_and_wait(serial, f"IOT:MQTT:{topic}:{index}:{state}", "IOT_MQTT")
        count += 1
    return count


def apply_http(serial: SerialPort, events: dict[str, Any]) -> int:
    count = 0
    for item in as_list(events.get("http")):
        if not isinstance(item, dict):
            continue
        method = str(item.get("method", "POST")).upper()[:8]
        path = str(item.get("path", "/api/device"))[:48]
        status = int(item.get("status", 200))
        send_and_wait(serial, f"IOT:HTTP:{method}:{path}:{status}", "IOT_HTTP")
        count += 1
    return count


def parse_state(line: str) -> dict[str, int | str]:
    match = STATE_RE.search(line)
    if not match:
        raise SystemExit(f"Could not parse IoT state: {line}")
    item: dict[str, int | str] = {}
    for key, value in match.groupdict().items():
        item[key] = value if key == "scene" else int(value)
    return item


def apply_events(serial: SerialPort, events: dict[str, Any]) -> dict[str, int | str]:
    send_and_wait(serial, "PING", "PONG")
    send_and_wait(serial, "PAGE:DEVICES", "IOT_PAGE page=DEVICES")

    ha_count = apply_home_assistant(serial, events)
    mqtt_count = apply_mqtt(serial, events)
    http_count = apply_http(serial, events)

    scene = str(events.get("scene", "HOME")).upper()
    if scene:
        send_and_wait(serial, f"SCENE:{scene}", "IOT_PAGE page=SCENE")

    send_and_wait(serial, "PAGE:LOG", "IOT_PAGE page=LOG")
    send_and_wait(serial, "PAGE:HOME", "IOT_PAGE page=HOME")
    serial.write_line("STATE?")
    state = serial.wait_for("IOT_STATE", 5)
    parsed = parse_state(state)
    if int(parsed["devices"]) < 4:
        raise SystemExit(f"Expected at least 4 devices, saw: {state}")
    if int(parsed["online"]) < 4:
        raise SystemExit(f"Expected all devices online, saw: {state}")
    if str(parsed["scene"]) != scene:
        raise SystemExit(f"Expected scene={scene}, saw: {state}")
    if int(parsed["mqtt"]) < mqtt_count:
        raise SystemExit(f"Expected at least {mqtt_count} MQTT events, saw: {state}")
    if int(parsed["http"]) < http_count:
        raise SystemExit(f"Expected at least {http_count} HTTP events, saw: {state}")

    return {
        "ha_count": ha_count,
        "mqtt_count": mqtt_count,
        "http_count": http_count,
        "scene": scene,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Relay smart-home events into the iot_control_panel serial protocol.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--mode", choices=["mock", "json", "http"], default="mock")
    parser.add_argument("--events-json")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    events = load_events(args)
    serial = SerialPort(args.port, args.baud)
    try:
        serial.wait_for("IOT_", args.timeout)
        summary = apply_events(serial, events)
    finally:
        serial.close()

    print(
        json.dumps(
            {
                "status": "ok",
                "mode": args.mode,
                **summary,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
