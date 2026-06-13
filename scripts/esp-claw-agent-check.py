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

READY_RE = re.compile(r"CLAW_(?:READY|PARTIAL) display=(?P<display>[01]) touch=(?P<touch>[01]) rules=(?P<rules>\d+)")
STATE_RE = re.compile(
    r"CLAW_STATE .*page=(?P<page>\S+) display=(?P<display>[01]) touch=(?P<touch>[01]) "
    r"rules=(?P<rules>\d+) events=(?P<events>\d+) actions=(?P<actions>\d+) "
    r"mcp=(?P<mcp>\d+) tools=(?P<tools>\d+) chats=(?P<chats>\d+) "
    r"memory=(?P<memory>\d+) lua=(?P<lua>\d+) "
    r"decision=(?P<decision>\S+) action=(?P<action>\S+)"
)
PAGE_RE = re.compile(r"CLAW_PAGE page=(?P<page>\S+) source=(?P<source>\S+)")


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
            if key in {"page", "decision", "action"}:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the ESP-Claw/OpenClaw Arduino agent harness.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--allow-touch-missing", action="store_true")
    args = parser.parse_args()

    collected: list[str] = []
    serial = SerialPort(args.port, args.baud)
    try:
        ready_line = serial.wait_for(
            lambda line: line.startswith("CLAW_READY")
            or line.startswith("CLAW_PARTIAL")
            or line.startswith("CLAW_STATE"),
            15,
            "CLAW_READY",
        )
        collected.append(ready_line)
        ready = READY_RE.search(ready_line)
        state_ready = STATE_RE.search(ready_line)
        if ready:
            if ready.group("display") != "1":
                raise SystemExit("ESP-Claw harness display did not report ready.")
            if ready.group("touch") != "1" and not args.allow_touch_missing:
                raise SystemExit("ESP-Claw harness touch did not report ready.")
        elif state_ready:
            if state_ready.group("display") != "1":
                raise SystemExit("ESP-Claw harness display did not report ready in state.")
            if state_ready.group("touch") != "1" and not args.allow_touch_missing:
                raise SystemExit("ESP-Claw harness touch did not report ready in state.")

        serial.write_line("PING")
        collected.append(serial.wait_for(lambda line: line == "PONG", 5, "PONG"))
        serial.write_line("CAPS?")
        collected.append(
            serial.wait_for(
                lambda line: line.startswith("CLAW_CAPS")
                and "loop=sense,reason,decide,act" in line
                and "mcp=server,client" in line
                and "lua=load" in line,
                5,
                "CLAW_CAPS",
            )
        )

        commands = [
            ("PAGE:RULES", "CLAW_PAGE", "page=RULES"),
            ("RULE:ADD:desk_shake:IMU_SHAKE:TOOL:light.toggle", "CLAW_RULE_ADDED", "name=desk_shake"),
            ("EVENT:IMU_SHAKE:strong", "CLAW_ACT", "action=TOOL:light.toggle"),
            ("LUA:LOAD:door_guard:DOOR_OPEN:TOOL:display.message", "CLAW_LUA_LOADED", "name=door_guard"),
            ("EVENT:DOOR_OPEN:front", "CLAW_ACT", "action=TOOL:display.message"),
            ("MCP:REGISTER:display.message:text", "CLAW_MCP_REGISTER", "tool=display.message"),
            ("MCP:CALL:display.message:hello-agent", "CLAW_MCP_CALL", "tool=display.message"),
            ("CHAT:when battery low dim display", "CLAW_RULE_ADDED", "name=chat_battery"),
            ("EVENT:BATTERY_LOW:18", "CLAW_ACT", "action=TOOL:display.dim"),
            ("MEM:PUT:goal:edge-agent", "CLAW_MEMORY_PUT", "tag=goal"),
            ("MEM:GET:goal", "CLAW_MEMORY_GET", "hit=1"),
            ("PAGE:MCP", "CLAW_PAGE", "page=MCP"),
            ("PAGE:MEMORY", "CLAW_PAGE", "page=MEMORY"),
            ("PAGE:HOME", "CLAW_PAGE", "page=HOME"),
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

        serial.write_line("EVENT:UNKNOWN_SENSOR:demo")
        collected.append(
            serial.wait_for(
                lambda line: line.startswith("CLAW_ACT") and "action=LLM:REQUEST" in line,
                5,
                "LLM fallback action",
            )
        )
        serial.write_line("STATE?")
        collected.append(serial.wait_for(lambda line: line.startswith("CLAW_STATE"), 5, "CLAW_STATE"))
        collected.extend(serial.read_lines(args.seconds))
    finally:
        serial.close()

    states = parse_states(collected)
    if not states:
        raise SystemExit("No CLAW_STATE lines captured.")
    latest = states[-1]
    pages = parse_pages(collected)

    if int(latest["rules"]) < 5:
        raise SystemExit(f"Expected at least 5 rules, saw {latest['rules']}")
    if int(latest["events"]) < 4:
        raise SystemExit(f"Expected at least 4 events, saw {latest['events']}")
    if int(latest["actions"]) < 5:
        raise SystemExit(f"Expected at least 5 actions, saw {latest['actions']}")
    if int(latest["mcp"]) < 1:
        raise SystemExit("Expected at least one MCP call.")
    if int(latest["tools"]) < 1:
        raise SystemExit("Expected at least one MCP tool registration.")
    if int(latest["chats"]) < 1:
        raise SystemExit("Expected at least one IM chat command.")
    if int(latest["memory"]) < 1:
        raise SystemExit("Expected at least one memory item.")
    if int(latest["lua"]) < 1:
        raise SystemExit("Expected at least one Lua-style rule load.")
    if "LLM:REQUEST" not in str(latest["action"]):
        raise SystemExit(f"Expected latest fallback action to be LLM:REQUEST, saw {latest['action']}")
    if not {"RULES", "MCP", "MEMORY", "HOME"}.issubset(set(pages)):
        raise SystemExit(f"Missing expected page flow, saw {pages}")

    print(
        "esp_claw_agent_summary "
        f"states={len(states)} page_flow={','.join(pages)} rules={latest['rules']} "
        f"events={latest['events']} actions={latest['actions']} mcp={latest['mcp']} "
        f"tools={latest['tools']} chats={latest['chats']} memory={latest['memory']} "
        f"lua={latest['lua']} latest_action={latest['action']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
