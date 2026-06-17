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
    r"NES_CONTRA_READY display=(?P<display>[01]) touch=(?P<touch>[01]) "
    r"mode=(?P<mode>\S+) target_mapper=(?P<mapper>\d+) rom=(?P<rom>\S+) frames=(?P<frames>\d+)"
)
STATE_RE = re.compile(
    r"NES_CONTRA_(?:FRAME|STATE) frame=(?P<frame>\d+) display=(?P<display>[01]) touch=(?P<touch>[01]) "
    r"mode=(?P<mode>\S+) target_mapper=(?P<mapper>\d+) rom=(?P<rom>\S+) buttons=(?P<buttons>\S+) "
    r"input_events=(?P<input_events>\d+) touch_events=(?P<touch_events>\d+)"
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
                    print(f"< {line}", flush=True)
                    lines.append(line)
        return lines

    def wait_for(self, predicate, timeout: float, label: str) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for line in self.read_lines(min(0.5, max(0.0, deadline - time.time()))):
                if predicate(line):
                    return line
        raise SystemExit(f"Timed out waiting for {label}")


def parse_state(lines: list[str]) -> list[dict[str, str]]:
    states: list[dict[str, str]] = []
    for line in lines:
        match = STATE_RE.search(line)
        if match:
            states.append(match.groupdict())
    return states


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the NES Contra emulator diagnostic lane.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--allow-touch-missing", action="store_true")
    args = parser.parse_args()

    collected: list[str] = []
    serial = SerialPort(args.port, args.baud)
    try:
        ready_line = serial.wait_for(
            lambda line: line.startswith("NES_CONTRA_READY") or line.startswith("NES_CONTRA_FRAME"),
            15,
            "NES_CONTRA_READY",
        )
        collected.append(ready_line)
        ready = READY_RE.search(ready_line)
        if ready:
            if ready.group("display") != "1":
                raise SystemExit("NES Contra display did not report ready.")
            if ready.group("touch") != "1" and not args.allow_touch_missing:
                raise SystemExit("NES Contra touch did not report ready.")
            if ready.group("mapper") != "2":
                raise SystemExit(f"Unexpected target mapper: {ready.group('mapper')}")

        serial.write_line("PING")
        collected.append(serial.wait_for(lambda line: line == "PONG", 5, "PONG"))
        serial.write_line("CAPS?")
        collected.append(serial.wait_for(lambda line: line.startswith("NES_CONTRA_CAPS"), 5, "NES_CONTRA_CAPS"))
        serial.write_line("ROM?")
        collected.append(serial.wait_for(lambda line: line.startswith("NES_CONTRA_ROM"), 5, "NES_CONTRA_ROM"))
        serial.write_line("INPUT:A")
        collected.append(
            serial.wait_for(
                lambda line: line.startswith("NES_CONTRA_INPUT") and "buttons=A" in line,
                5,
                "NES_CONTRA_INPUT",
            )
        )
        serial.write_line("STATE?")
        collected.append(serial.wait_for(lambda line: line.startswith("NES_CONTRA_STATE"), 5, "NES_CONTRA_STATE"))
        collected.extend(serial.read_lines(args.seconds))
    finally:
        serial.close()

    states = parse_state(collected)
    if not states:
        raise SystemExit("No NES_CONTRA_STATE or NES_CONTRA_FRAME lines captured.")

    max_frame = max(int(item["frame"]) for item in states)
    if max_frame == 0:
        raise SystemExit("Frame loop did not advance.")

    latest = states[-1]
    if latest["display"] != "1":
        raise SystemExit("Display readiness was lost.")
    if latest["mapper"] != "2":
        raise SystemExit(f"Unexpected mapper in latest state: {latest['mapper']}")
    if int(latest["input_events"]) < 1:
        raise SystemExit("Serial input injection was not recorded.")

    print(
        "nes_contra_summary "
        f"mode={latest['mode']} target_mapper={latest['mapper']} rom={latest['rom']} "
        f"display={latest['display']} touch={latest['touch']} frames={max_frame} "
        f"input_events={latest['input_events']} touch_events={latest['touch_events']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
