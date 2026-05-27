"""
Wildlife model registry.

Built-in models (auto-downloaded by ultralytics on first use from ultralytics.com):
  yolo11n, yolo11s, yolo11m, yolov8n, yolov8s, yolov8m

Custom models: place .pt / .onnx / .engine files in the  models/  directory at
the project root.  Well-known filenames (e.g. golden_eagle.pt) receive enriched
metadata; any other .pt file is listed generically.

For North American wildlife, pre-trained custom models are hosted in the
companion repository:  https://github.com/WyoSoC/Wildlife-YOLO-Models
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional

# Project-root  models/  directory (auto-created on first call to models_dir())
_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models",
)

# COCO class IDs relevant for wildlife detection with generic YOLO models
COCO_BIRD      = 14
COCO_CAT       = 15
COCO_DOG       = 16
COCO_HORSE     = 17
COCO_SHEEP     = 18
COCO_COW       = 19
COCO_ELEPHANT  = 20
COCO_BEAR      = 21
COCO_ZEBRA     = 22
COCO_GIRAFFE   = 23

_COCO_WILDLIFE = [COCO_BIRD, COCO_CAT, COCO_DOG, COCO_HORSE, COCO_SHEEP,
                  COCO_COW, COCO_ELEPHANT, COCO_BEAR, COCO_ZEBRA, COCO_GIRAFFE]


@dataclass
class ModelInfo:
    name: str                               # unique key, e.g. "yolo11n" or "golden_eagle"
    path: str                               # value passed to YOLO(), e.g. "yolo11n.pt"
    description: str                        # shown in UI
    detect_classes: Optional[list[int]] = None  # None = all model classes
    species: list[str] = field(default_factory=list)
    source: str = "ultralytics"             # "ultralytics" | "custom" | "megadetector"
    auto_download: bool = True              # ultralytics fetches on first use


# ── Built-in catalog (always listed; weights auto-downloaded by ultralytics) ───

_BUILTIN: list[ModelInfo] = [
    ModelInfo(
        name="yolo11n",
        path="yolo11n.pt",
        description="YOLO11 Nano — fastest, general wildlife (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
    ModelInfo(
        name="yolo11s",
        path="yolo11s.pt",
        description="YOLO11 Small — balanced speed/accuracy (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
    ModelInfo(
        name="yolo11m",
        path="yolo11m.pt",
        description="YOLO11 Medium — higher accuracy (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
    ModelInfo(
        name="yolov8n",
        path="yolov8n.pt",
        description="YOLOv8 Nano — lightweight baseline (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
    ModelInfo(
        name="yolov8s",
        path="yolov8s.pt",
        description="YOLOv8 Small — recommended default (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
    ModelInfo(
        name="yolov8m",
        path="yolov8m.pt",
        description="YOLOv8 Medium — best accuracy among built-ins (COCO)",
        detect_classes=_COCO_WILDLIFE,
        species=["bird", "bear", "horse", "sheep", "cow", "elephant", "zebra", "giraffe"],
        source="ultralytics",
    ),
]

# ── Well-known custom model metadata (unlocked when the .pt exists in models/) ─

_CUSTOM_CATALOG: dict[str, ModelInfo] = {
    "megadetector_v5.pt": ModelInfo(
        name="megadetector_v5",
        path="megadetector_v5.pt",
        description="MegaDetector v5 — camera-trap specialist (animals / humans / vehicles)",
        detect_classes=None,
        species=["animal (generic)", "human", "vehicle"],
        source="megadetector",
        auto_download=False,
    ),
    "golden_eagle.pt": ModelInfo(
        name="golden_eagle",
        path="golden_eagle.pt",
        description="Golden Eagle (WyoSoC Wildlife Models)",
        detect_classes=None,
        species=["golden eagle"],
        source="custom",
        auto_download=False,
    ),
    "pronghorn.pt": ModelInfo(
        name="pronghorn",
        path="pronghorn.pt",
        description="Pronghorn (WyoSoC Wildlife Models)",
        detect_classes=None,
        species=["pronghorn"],
        source="custom",
        auto_download=False,
    ),
    "bighorn_sheep.pt": ModelInfo(
        name="bighorn_sheep",
        path="bighorn_sheep.pt",
        description="Bighorn Sheep (WyoSoC Wildlife Models)",
        detect_classes=None,
        species=["bighorn sheep"],
        source="custom",
        auto_download=False,
    ),
    "bison.pt": ModelInfo(
        name="bison",
        path="bison.pt",
        description="Bison (WyoSoC Wildlife Models)",
        detect_classes=None,
        species=["bison"],
        source="custom",
        auto_download=False,
    ),
    "north_american_wildlife.pt": ModelInfo(
        name="north_american_wildlife",
        path="north_american_wildlife.pt",
        description="North American Wildlife — multi-species (WyoSoC Wildlife Models)",
        detect_classes=None,
        species=["golden eagle", "pronghorn", "bighorn sheep", "bison",
                 "mule deer", "elk", "coyote"],
        source="custom",
        auto_download=False,
    ),
}


# ── Public API ─────────────────────────────────────────────────────────────────

def list_models() -> list[ModelInfo]:
    """
    Built-in models + any .pt / .onnx / .engine files found in  models/ .
    Custom models with well-known filenames receive enriched metadata.
    """
    result: list[ModelInfo] = list(_BUILTIN)

    if os.path.isdir(_MODELS_DIR):
        for fname in sorted(os.listdir(_MODELS_DIR)):
            if not fname.endswith((".pt", ".onnx", ".engine")):
                continue
            abs_path = os.path.join(_MODELS_DIR, fname)
            if fname in _CUSTOM_CATALOG:
                tmpl = _CUSTOM_CATALOG[fname]
                result.append(ModelInfo(
                    name=tmpl.name,
                    path=abs_path,
                    description=tmpl.description,
                    detect_classes=tmpl.detect_classes,
                    species=tmpl.species,
                    source=tmpl.source,
                    auto_download=False,
                ))
            else:
                stem = os.path.splitext(fname)[0]
                result.append(ModelInfo(
                    name=stem,
                    path=abs_path,
                    description=f"{stem} (custom)",
                    source="custom",
                    auto_download=False,
                ))

    return result


def get_model(name: str) -> Optional[ModelInfo]:
    return next((m for m in list_models() if m.name == name), None)


def models_dir() -> str:
    os.makedirs(_MODELS_DIR, exist_ok=True)
    return _MODELS_DIR
