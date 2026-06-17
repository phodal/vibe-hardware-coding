#!/usr/bin/env python3
import argparse
import hashlib
import pathlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CONTRA_DIR = (ROOT / ".." / "nes-contra-us").resolve()
DEFAULT_BASEROM = DEFAULT_CONTRA_DIR / "baserom.nes"
DEFAULT_CONTRA_ROM = DEFAULT_CONTRA_DIR / "contra.nes"
EXPECTED_BASEROM_MD5 = "7bdad8b4a7a56a634c9649d20bd3011b"


@dataclass
class ToolState:
    name: str
    path: str


@dataclass
class RomHeader:
    path: pathlib.Path
    size: int
    sha256: str
    prg_banks: int
    chr_banks: int
    mapper: int
    mirroring: str
    trainer: bool
    battery: bool


def hash_file(path: pathlib.Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_tools() -> list[ToolState]:
    return [ToolState(name, shutil.which(name) or "missing") for name in ("ca65", "ld65", "cc65", "cl65")]


def parse_ines(path: pathlib.Path) -> RomHeader:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError("file is smaller than an iNES header")
    if data[:4] != b"NES\x1a":
        raise ValueError("missing iNES magic")
    flags6 = data[6]
    flags7 = data[7]
    mapper = (flags6 >> 4) | (flags7 & 0xF0)
    mirroring = "vertical" if flags6 & 0x01 else "horizontal"
    return RomHeader(
        path=path,
        size=len(data),
        sha256=hash_file(path, "sha256"),
        prg_banks=data[4],
        chr_banks=data[5],
        mapper=mapper,
        mirroring=mirroring,
        trainer=bool(flags6 & 0x04),
        battery=bool(flags6 & 0x02),
    )


def format_bool(value: bool) -> str:
    return "1" if value else "0"


def build_contra(contra_dir: pathlib.Path) -> int:
    build_script = contra_dir / "build.sh"
    if not build_script.exists():
        print(f"nes_contra_preflight_issue build_script_missing path={build_script}")
        return 1
    completed = subprocess.run(["bash", str(build_script)], cwd=contra_dir)
    return completed.returncode


def print_tool_summary(tools: list[ToolState]) -> None:
    for tool in tools:
        print(f"nes_contra_tool name={tool.name} path={tool.path}")


def print_header(prefix: str, header: RomHeader) -> None:
    print(
        f"{prefix} "
        f"path={header.path} size={header.size} sha256={header.sha256} "
        f"prg_banks={header.prg_banks} chr_banks={header.chr_banks} mapper={header.mapper} "
        f"mirroring={header.mirroring} trainer={format_bool(header.trainer)} battery={format_bool(header.battery)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local Contra ROM/toolchain readiness for the NES emulator lane.")
    parser.add_argument("--contra-dir", default=str(DEFAULT_CONTRA_DIR))
    parser.add_argument("--baserom", default=str(DEFAULT_BASEROM))
    parser.add_argument("--rom", default=str(DEFAULT_CONTRA_ROM))
    parser.add_argument("--build-rom", action="store_true", help="Run build.sh when baserom and cc65 tools are present.")
    parser.add_argument("--require-rom", action="store_true", help="Fail when no .nes ROM is available.")
    parser.add_argument("--require-tools", action="store_true", help="Fail when cc65 tools are missing.")
    args = parser.parse_args()

    contra_dir = pathlib.Path(args.contra_dir).expanduser().resolve()
    baserom = pathlib.Path(args.baserom).expanduser().resolve()
    rom = pathlib.Path(args.rom).expanduser().resolve()

    tools = find_tools()
    missing_tools = [tool.name for tool in tools if tool.path == "missing"]
    print(f"nes_contra_source path={contra_dir} exists={format_bool(contra_dir.exists())}")
    print_tool_summary(tools)

    if baserom.exists():
        md5 = hash_file(baserom, "md5")
        print(
            f"nes_contra_baserom path={baserom} exists=1 size={baserom.stat().st_size} "
            f"md5={md5} expected_md5={EXPECTED_BASEROM_MD5} match={format_bool(md5.lower() == EXPECTED_BASEROM_MD5)}"
        )
    else:
        print(f"nes_contra_baserom path={baserom} exists=0")

    if args.build_rom:
        if not baserom.exists():
            print("nes_contra_preflight_issue build_skipped reason=missing-baserom")
        elif missing_tools:
            print(f"nes_contra_preflight_issue build_skipped reason=missing-tools tools={','.join(missing_tools)}")
        else:
            build_rc = build_contra(contra_dir)
            print(f"nes_contra_build returncode={build_rc}")
            if build_rc != 0:
                return build_rc

    header: Optional[RomHeader] = None
    if rom.exists():
        try:
            header = parse_ines(rom)
            print_header("nes_contra_rom", header)
        except ValueError as exc:
            print(f"nes_contra_preflight_issue rom_invalid path={rom} error={exc}")
            return 1
    else:
        print(f"nes_contra_rom path={rom} exists=0")

    issues: list[str] = []
    if not contra_dir.exists():
        issues.append("missing-source")
    if missing_tools and args.require_tools:
        issues.append("missing-tools")
    if header is None:
        if args.require_rom:
            issues.append("missing-rom")
    else:
        if header.mapper != 2:
            issues.append(f"unsupported-mapper-{header.mapper}")
        if header.prg_banks != 8:
            issues.append(f"unexpected-prg-banks-{header.prg_banks}")
        if header.chr_banks != 0:
            issues.append(f"unexpected-chr-banks-{header.chr_banks}")

    status = "ready" if not issues and header is not None else ("blocked" if issues else "missing-rom")
    print(
        "nes_contra_preflight_summary "
        f"status={status} source={format_bool(contra_dir.exists())} "
        f"baserom={format_bool(baserom.exists())} rom={format_bool(header is not None)} "
        f"tools_missing={','.join(missing_tools) if missing_tools else 'none'} "
        f"issues={','.join(issues) if issues else 'none'}"
    )
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
