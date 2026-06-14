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


DEFAULT_EXPECT_ANY = [
    "XiaoZhi",
    "Xiaozhi",
    "xiaozhi",
    "小智",
    "验证码",
    "激活",
    "activation",
    "Activation",
    "配网",
]
DEFAULT_REJECT = [
    "WIFI_CONNECTIVITY",
    "DISPLAY_OCR",
    "CLOUD_AI",
    "SENSOR_STATUS",
    "POWER_LIFECYCLE",
    "TOUCH_STATUS",
    "INTERACTION_DASHBOARD",
]


def split_markers(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def marker_label(marker: str) -> str:
    return marker.replace(" ", "_").replace(",", "_")


def set_line(fd: int, mask: int, enabled: bool) -> None:
    request = termios.TIOCMBIS if enabled else termios.TIOCMBIC
    fcntl.ioctl(fd, request, struct.pack("I", mask))


def configure(fd: int, baud: int) -> None:
    speed = BAUDS.get(baud)
    if speed is None:
        raise SystemExit(f"Unsupported baud: {baud}")
    attrs = termios.tcgetattr(fd)
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
    set_line(fd, termios.TIOCM_DTR, False)
    set_line(fd, termios.TIOCM_RTS, True)
    time.sleep(sleep_seconds)
    set_line(fd, termios.TIOCM_RTS, False)
    time.sleep(sleep_seconds)


def capture_serial(port: str, baud: int, seconds: float, log_path: pathlib.Path, pulse_rts: bool) -> str:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure(fd, baud)
        if pulse_rts:
            pulse_reset(fd, 0.12)
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
    finally:
        os.close(fd)


def count_lines(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def require_runtime(text: str, args: argparse.Namespace) -> tuple[list[str], list[str]]:
    rejected = [marker for marker in args.reject if marker in text]
    if rejected:
        raise SystemExit(f"Rejected non-XiaoZhi marker(s) found: {', '.join(rejected)}")

    lines = count_lines(text)
    byte_count = len(text.encode("utf-8"))
    if lines < args.min_lines:
        raise SystemExit(f"Too few runtime lines: got {lines}, need {args.min_lines}")
    if byte_count < args.min_bytes:
        raise SystemExit(f"Too few runtime bytes: got {byte_count}, need {args.min_bytes}")

    missing_all = [marker for marker in args.expect_all if marker not in text]
    if missing_all:
        raise SystemExit(f"Missing required marker(s): {', '.join(missing_all)}")

    matched_any = [marker for marker in args.expect_any if marker in text]
    if args.expect_any and not matched_any:
        raise SystemExit(f"Missing any XiaoZhi runtime marker from: {', '.join(args.expect_any)}")

    return matched_any, [marker for marker in args.expect_all if marker in text]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate XiaoZhi runtime serial evidence without flashing or audio.")
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--input-log", help="Validate an existing log instead of opening a serial port.")
    parser.add_argument("--pulse-rts", action="store_true", help="Reset the ESP32-S3 while capture is already open.")
    parser.add_argument("--expect-any", action="append", default=[], help="Comma-separated markers; at least one must match.")
    parser.add_argument("--expect-all", action="append", default=[], help="Comma-separated markers; all must match.")
    parser.add_argument("--reject", action="append", default=[], help="Comma-separated markers that must not match.")
    parser.add_argument("--min-lines", type=int, default=1)
    parser.add_argument("--min-bytes", type=int, default=1)
    args = parser.parse_args()

    args.expect_any = [marker for value in args.expect_any for marker in split_markers(value)] or DEFAULT_EXPECT_ANY
    args.expect_all = [marker for value in args.expect_all for marker in split_markers(value)]
    args.reject = [marker for value in args.reject for marker in split_markers(value)] or DEFAULT_REJECT

    log_path = pathlib.Path(args.log)
    if args.input_log:
        text = pathlib.Path(args.input_log).read_text(encoding="utf-8", errors="replace")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(text, encoding="utf-8")
    else:
        if not args.port:
            raise SystemExit("--port is required unless --input-log is used")
        text = capture_serial(args.port, args.baud, args.seconds, log_path, args.pulse_rts)

    matched_any, matched_all = require_runtime(text, args)
    print(
        "xiaozhi_runtime_summary "
        f"status=ok log={log_path} bytes={len(text.encode('utf-8'))} lines={count_lines(text)} "
        f"matched_any={','.join(marker_label(marker) for marker in matched_any) or 'none'} "
        f"matched_all={','.join(marker_label(marker) for marker in matched_all) or 'none'} "
        "destructive=0 audio=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
