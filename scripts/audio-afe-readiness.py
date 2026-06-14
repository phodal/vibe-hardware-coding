#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "audio-afe-profile.tsv"
DEFAULT_SKETCH = ROOT / "sketches" / "audio_vad_probe"
DEFAULT_BUILD = ROOT / ".arduino-build" / "audio_vad_probe"
DEFAULT_CHECKER = ROOT / "scripts" / "audio-vad-check.py"

EXPECTED_PROFILE = {
    "es7210_capture": ("implemented", "ES7210"),
    "vad": ("implemented", "ESP-SR VAD"),
    "aec": ("planned", "ESP-SR AFE AEC"),
    "noise_suppression": ("planned", "ESP-SR AFE NS"),
    "wakenet": ("planned", "ESP-SR WakeNet"),
}

SOURCE_MARKERS = {
    "es7210_capture": [
        ("audio_vad_probe.ino", "#include <driver/i2s.h>"),
        ("audio_vad_probe.ino", "es7210_adc_init"),
        ("audio_vad_probe.ino", "PIN_ES7210_BCLK"),
        ("pin_config.h", "PIN_ES7210_DIN"),
        ("pin_config.h", "PIN_ES7210_MCLK"),
        ("es7210.cpp", "es7210_adc_init"),
        ("es7210.h", "es7210_adc_config_i2s"),
    ],
    "vad": [
        ("audio_vad_probe.ino", "#include <esp_vad.h>"),
        ("audio_vad_probe.ino", "vad_create"),
        ("audio_vad_probe.ino", "vad_process"),
        ("audio_vad_probe.ino", "AUDIO_SPEECH_DETECTED"),
    ],
    "aec": [],
    "noise_suppression": [],
    "wakenet": [],
}

ARTIFACTS = [
    "audio_vad_probe.ino.bin",
    "audio_vad_probe.ino.bootloader.bin",
    "audio_vad_probe.ino.partitions.bin",
    "audio_vad_probe.ino.elf",
]


def load_profile(path: pathlib.Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = {row["id"].strip(): {k: (v or "").strip() for k, v in row.items()} for row in reader}
    missing = sorted(set(EXPECTED_PROFILE) - set(rows))
    if missing:
        raise SystemExit(f"audio_afe_readiness missing_profile_rows={','.join(missing)}")
    for item_id, (status, component) in EXPECTED_PROFILE.items():
        row = rows[item_id]
        if row["status"] != status or row["component"] != component:
            raise SystemExit(
                "audio_afe_readiness invalid_profile "
                f"id={item_id} expected_status={status} actual_status={row['status']} "
                f"expected_component={component!r} actual_component={row['component']!r}"
            )
    return rows


def has_marker(sketch: pathlib.Path, relative: str, marker: str) -> bool:
    path = sketch / relative
    if not path.is_file():
        return False
    return marker in path.read_text(encoding="utf-8", errors="replace")


def source_state(item_id: str, sketch: pathlib.Path) -> str:
    markers = SOURCE_MARKERS[item_id]
    if not markers:
        return "source-integration-required"
    missing = [f"{relative}:{marker}" for relative, marker in markers if not has_marker(sketch, relative, marker)]
    return "ready" if not missing else "missing"


def artifact_state(build: pathlib.Path) -> str:
    missing = [name for name in ARTIFACTS if not (build / name).is_file()]
    return "ready" if not missing else "missing"


def checker_state(checker: pathlib.Path) -> str:
    if not checker.is_file():
        return "missing"
    text = checker.read_text(encoding="utf-8", errors="replace")
    required = ["--stimulus-command", "--min-rms-delta", "--require-speech"]
    return "ready" if all(marker in text for marker in required) else "missing"


def next_action(row: dict[str, str], source: str, build: str, checker: str) -> str:
    if row["status"] == "planned":
        return "add-esp-sr-source-integration-and-physical-audio-fixture"
    if source != "ready":
        return "restore-source-markers"
    if build != "ready":
        return "run-make-audio-vad-build"
    if checker != "ready":
        return "restore-host-audio-checker-options"
    return "schedule-physical-audio-smoke"


def main() -> int:
    parser = argparse.ArgumentParser(description="Report no-audio readiness for the audio front-end lane.")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--sketch", default=str(DEFAULT_SKETCH))
    parser.add_argument("--build", default=str(DEFAULT_BUILD))
    parser.add_argument("--checker", default=str(DEFAULT_CHECKER))
    args = parser.parse_args()

    profile = load_profile(pathlib.Path(args.profile))
    sketch = pathlib.Path(args.sketch)
    build = pathlib.Path(args.build)
    checker = pathlib.Path(args.checker)

    build_ready = artifact_state(build)
    checker_ready = checker_state(checker)
    implemented = planned = source_ready = source_required = physical_required = 0

    for item_id in EXPECTED_PROFILE:
        row = profile[item_id]
        source = source_state(item_id, sketch)
        if row["status"] == "implemented":
            implemented += 1
        else:
            planned += 1
        if source == "ready":
            source_ready += 1
        if "source-integration-required" in row["validation"]:
            source_required += 1
        if "physical-smoke" in row["validation"]:
            physical_required += 1

        print(
            "audio_afe_readiness "
            f"id={item_id} status={row['status']} component={row['component'].replace(' ', '_')} "
            f"source={source} build={build_ready if row['status'] == 'implemented' else 'not_required'} "
            f"checker={checker_ready if row['status'] == 'implemented' else 'not_required'} "
            f"validation={row['validation'].replace(',', '+')} "
            f"next={next_action(row, source, build_ready, checker_ready)} audio=0"
        )

    print(
        "audio_afe_readiness_summary "
        f"components={len(EXPECTED_PROFILE)} implemented={implemented} planned={planned} "
        f"source_ready={source_ready} source_integration_required={source_required} "
        f"physical_audio_required={physical_required} build={build_ready} checker={checker_ready} "
        "destructive=0 audio=0"
    )
    return 0 if build_ready == "ready" and checker_ready == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
