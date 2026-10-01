from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "best.pt"
DEFAULT_DATA_PATH = PROJECT_ROOT / "dataset_yolo" / "data.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation_runs"
DEFAULT_JSON_PATH = PROJECT_ROOT / "evaluation_results.json"
STATIC_EVAL_DIR = PROJECT_ROOT / "static" / "evaluation"


def _to_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, np.ndarray)):
        return [float(v) for v in value.tolist()] if hasattr(value, "tolist") else [float(v) for v in value]
    if isinstance(value, (int, float, np.floating, np.integer)):
        return [float(value)]
    return [float(value)]


def _safe_index(values: list, idx: int) -> float:
    if not values:
        return 0.0
    if idx < 0:
        idx = 0
    if idx >= len(values):
        idx = len(values) - 1
    return float(values[idx])


def _load_class_names(data_path: Path) -> list[str]:
    with open(data_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    names = config.get("names") or []
    return [str(name).strip() for name in names if str(name).strip()]


def _find_confusion_matrix(run_dir: Path) -> Path | None:
    matches = sorted(run_dir.rglob("confusion_matrix*.png"))
    if matches:
        return matches[0]
    matches = sorted(run_dir.rglob("*.png"))
    for match in matches:
        name = match.name.lower()
        if "confusion" in name or "matrix" in name:
            return match
    return None


def _save_confusion_matrix(confusion_matrix_path: Path | None) -> str | None:
    if confusion_matrix_path is None:
        return None

    STATIC_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    output_image = STATIC_EVAL_DIR / "confusion_matrix.png"
    shutil.copy2(confusion_matrix_path, output_image)
    return str(output_image.relative_to(PROJECT_ROOT))


def run_evaluation(model_path: str | Path | None = None, data_yaml: str | Path | None = None):
    model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
    data_yaml = Path(data_yaml) if data_yaml else DEFAULT_DATA_PATH

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}. Place your trained model as best.pt in the project root.")
    if not data_yaml.exists():
        raise FileNotFoundError(f"YOLO data.yaml not found: {data_yaml}")

    class_names = _load_class_names(data_yaml)
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(model_path))
    results = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=640,
        conf=0.001,
        iou=0.6,
        project=str(output_dir),
        name="eval_run",
        exist_ok=True,
        save_json=True,
        save_conf=True,
        plots=True,
        verbose=False,
    )

    metrics = results.box
    precision = float(np.nanmean(_to_list(getattr(metrics, "p", None))) if _to_list(getattr(metrics, "p", None)) else 0.0)
    recall = float(np.nanmean(_to_list(getattr(metrics, "r", None))) if _to_list(getattr(metrics, "r", None)) else 0.0)
    f1 = float(np.nanmean(_to_list(getattr(metrics, "f1", None))) if _to_list(getattr(metrics, "f1", None)) else 0.0)
    map50 = float(np.nanmean(_to_list(getattr(metrics, "map50", None))) if _to_list(getattr(metrics, "map50", None)) else 0.0)
    map50_95 = float(np.nanmean(_to_list(getattr(metrics, "map", None))) if _to_list(getattr(metrics, "map", None)) else 0.0)

    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    confusion_matrix_path = _find_confusion_matrix(output_dir / "eval_run")
    confusion_matrix_rel = _save_confusion_matrix(confusion_matrix_path)

    per_class_rows = []
    precision_values = _to_list(getattr(metrics, "p", None))
    recall_values = _to_list(getattr(metrics, "r", None))
    f1_values = _to_list(getattr(metrics, "f1", None))
    map50_values = _to_list(getattr(metrics, "map50", None))
    map95_values = _to_list(getattr(metrics, "map", None))

    for idx, class_name in enumerate(class_names):
        per_class_rows.append({
            "class": class_name,
            "precision": round(_safe_index(precision_values, idx), 6),
            "recall": round(_safe_index(recall_values, idx), 6),
            "f1": round(_safe_index(f1_values, idx), 6),
            "mAP50": round(_safe_index(map50_values, idx), 6),
            "mAP50_95": round(_safe_index(map95_values, idx), 6),
        })

    test_images = 0
    test_images_dir = PROJECT_ROOT / "dataset_yolo" / "images" / "test"
    if test_images_dir.exists():
        test_images = len([p for p in test_images_dir.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}])

    payload = {
        "model": str(model_path.name),
        "data_yaml": str(data_yaml),
        "test_images": test_images,
        "metrics": {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1_score": round(f1, 6),
            "mAP50": round(map50, 6),
            "mAP50_95": round(map50_95, 6),
        },
        "per_class": per_class_rows,
        "confusion_matrix": confusion_matrix_rel,
        "classes": class_names,
    }

    with open(DEFAULT_JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return payload


if __name__ == "__main__":
    result = run_evaluation()
    print(json.dumps(result["metrics"], indent=2))
