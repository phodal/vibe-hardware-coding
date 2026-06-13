#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "config" / "tinyml-imu-model.json"


def load_model(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "hash", "type", "features", "gyro_scale", "prototypes", "validation"}
    missing = required - set(payload)
    if missing:
        raise SystemExit(f"{path} missing keys: {sorted(missing)}")
    if payload["type"] != "nearest_centroid":
        raise SystemExit(f"Unsupported model type: {payload['type']}")
    if len(payload["features"]) != 6:
        raise SystemExit("Expected six IMU features.")
    if not payload["prototypes"]:
        raise SystemExit("Expected at least one prototype.")
    if not payload["validation"]:
        raise SystemExit("Expected validation samples.")
    return payload


def scaled_distance(sample: list[float], prototype: list[float], gyro_scale: float) -> float:
    total = 0.0
    for index, (left, right) in enumerate(zip(sample, prototype, strict=True)):
        scale = gyro_scale if index >= 3 else 1.0
        total += ((left - right) / scale) ** 2
    return math.sqrt(total)


def classify(model: dict[str, Any], sample: list[float]) -> tuple[str, float, float]:
    gyro_scale = float(model["gyro_scale"])
    best_label = ""
    best_distance = float("inf")
    for item in model["prototypes"]:
        label = str(item["label"])
        features = [float(value) for value in item["features"]]
        distance = scaled_distance(sample, features, gyro_scale)
        if distance < best_distance:
            best_distance = distance
            best_label = label
    confidence = max(0.5, min(0.99, 1.0 / (1.0 + best_distance)))
    return best_label, confidence, best_distance


def evaluate(model: dict[str, Any]) -> tuple[int, int, float]:
    correct = 0
    total = 0
    min_confidence = 1.0
    for item in model["validation"]:
        expected = str(item["label"])
        sample = [float(value) for value in item["features"]]
        actual, confidence, _ = classify(model, sample)
        total += 1
        min_confidence = min(min_confidence, confidence)
        if actual == expected:
            correct += 1
        else:
            print(f"tinyml_model_miss expected={expected} actual={actual} sample={sample}")
    return correct, total, min_confidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the TinyML IMU centroid model metadata and validation set.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--min-accuracy", type=float, default=0.95)
    args = parser.parse_args()

    model = load_model(Path(args.model))
    correct, total, min_confidence = evaluate(model)
    accuracy = correct / total if total else 0.0
    expected_accuracy = float(model.get("validation_accuracy", 0.0))
    if abs(accuracy - expected_accuracy) > 0.0001:
      raise SystemExit(f"Model metadata validation_accuracy={expected_accuracy:.3f} but measured {accuracy:.3f}")
    print(
        "tinyml_model_summary "
        f"name={model['name']} hash={model['hash']} prototypes={len(model['prototypes'])} "
        f"validation={total} accuracy={accuracy:.3f} min_confidence={min_confidence:.3f}"
    )
    if accuracy < args.min_accuracy:
        raise SystemExit(f"accuracy {accuracy:.3f} < {args.min_accuracy:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
