#!/usr/bin/env python3
import argparse
import fcntl
import os
import pathlib
import select
import struct
import sys
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


def set_line(fd: int, mask: int, enabled: bool) -> None:
    request = termios.TIOCMBIS if enabled else termios.TIOCMBIC
    fcntl.ioctl(fd, request, struct.pack("I", mask))


def configure(fd: int, baud: int) -> None:
    attrs = termios.tcgetattr(fd)
    speed = BAUDS.get(baud, termios.B115200)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def pulse_reset(fd: int, sleep_seconds: float) -> None:
    # ESP32-S3 USB Serial/JTAG reset follows the common esptool pattern:
    # keep GPIO0 released through DTR, assert RTS briefly to hold EN low,
    # then release RTS so the app firmware starts while capture is active.
    set_line(fd, termios.TIOCM_DTR, False)
    set_line(fd, termios.TIOCM_RTS, True)
    time.sleep(sleep_seconds)
    set_line(fd, termios.TIOCM_RTS, False)
    time.sleep(sleep_seconds)


def capture(fd: int, seconds: float, log_path: pathlib.Path) -> str:
    deadline = time.monotonic() + seconds
    chunks: list[bytes] = []
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as handle:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], 0.1)
            if not readable:
                continue
            data = os.read(fd, 4096)
            if not data:
                continue
            chunks.append(data)
            handle.write(data)
            handle.flush()
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    return b"".join(chunks).decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture serial output with optional RTS reset pulse.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--expect", default="")
    parser.add_argument("--pulse-rts", action="store_true")
    parser.add_argument("--pulse-seconds", type=float, default=0.12)
    args = parser.parse_args()

    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure(fd, args.baud)
        if args.pulse_rts:
            pulse_reset(fd, args.pulse_seconds)
        text = capture(fd, args.seconds, pathlib.Path(args.log))
    finally:
        os.close(fd)

    expected = args.expect
    if expected and expected not in text:
        print(f"serial_capture expected_missing text={expected!r} log={args.log}", file=sys.stderr)
        return 1
    print(f"serial_capture_summary status=ok log={args.log} bytes={len(text.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
