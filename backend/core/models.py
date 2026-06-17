"""
Wildlife model registry.

Custom models: place .pt / .onnx / .engine files in the  models/  directory at
the project root.  Well-known filenames receive enriched metadata; any other
.pt file is listed generically.

Pre-trained custom models are hosted on HuggingFace under the UWyo organisation:
  https://huggingface.co/UWyo
Download them via  POST /api/models/{name}/download  or by running:
  python /path/to/Wildlife-YOLO-Models/scripts/download_models.py --model golden_eagle
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional

_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models",
)

HF_ORG = "UWyo"

# COCO class IDs for wildlife-adjacent categories — used as a coarse filter
# when falling back to a generic YOLO26 COCO model.
_COCO_WILDLIFE = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]


@dataclass
class ModelInfo:
    name:           str
    path:           str                        # value passed to YOLO()
    description:    str
    detect_classes: Optional[list[int]] = None # None = all model classes
    species:        list[str] = field(default_factory=list)
    source:         str = "ultralytics"        # "ultralytics" | "uwyo" | "custom" | "megadetector"
    auto_download:  bool = True                # can be fetched automatically
    repo_id:        Optional[str] = None       # HuggingFace repo ID
    hf_filename:    str = "best.pt"            # filename within the HF repo
    downloaded:     bool = True                # False = .pt not yet on disk


# ── UWyo wildlife catalog ──────────────────────────────────────────────────────
# Always listed in the API regardless of whether the .pt is on disk.
# `downloaded` is set dynamically in list_models().

_WILDLIFE_CATALOG: dict[str, ModelInfo] = {
    "north_american_wildlife.pt": ModelInfo(
        name="north_american_wildlife",
        path="north_american_wildlife.pt",
        description="North American Wildlife — 25 species, YOLO26m",
        detect_classes=None,
        species=[
            "golden eagle", "pronghorn", "bighorn sheep", "bison",
            "mule deer", "elk", "coyote", "grizzly bear", "gray wolf",
            "moose", "pika", "swift fox", "mountain lion", "river otter",
            "black bear", "bald eagle", "red-tailed hawk", "osprey",
            "sage grouse", "trumpeter swan", "beaver", "raven",
            "prairie dog", "badger", "bobcat",
        ],
        source="uwyo",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-north-american",
        hf_filename="best.pt",
    ),
    "golden_eagle.pt": ModelInfo(
        name="golden_eagle",
        path="golden_eagle.pt",
        description="Golden Eagle — YOLO26s, single-class",
        detect_classes=None,
        species=["golden eagle"],
        source="uwyo",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-golden-eagle",
        hf_filename="best.pt",
    ),
    "pronghorn.pt": ModelInfo(
        name="pronghorn",
        path="pronghorn.pt",
        description="Pronghorn — YOLO26s, single-class",
        detect_classes=None,
        species=["pronghorn"],
        source="uwyo",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-pronghorn",
        hf_filename="best.pt",
    ),
    "bighorn_sheep.pt": ModelInfo(
        name="bighorn_sheep",
        path="bighorn_sheep.pt",
        description="Bighorn Sheep — YOLO26s, single-class",
        detect_classes=None,
        species=["bighorn sheep"],
        source="uwyo",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-bighorn-sheep",
        hf_filename="best.pt",
    ),
    "bison.pt": ModelInfo(
        name="bison",
        path="bison.pt",
        description="Bison — YOLO26s, single-class",
        detect_classes=None,
        species=["bison"],
        source="uwyo",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-bison",
        hf_filename="best.pt",
    ),
    "megadetector_v5.pt": ModelInfo(
        name="megadetector_v5",
        path="megadetector_v5.pt",
        description="MegaDetector v5 — camera-trap specialist (animal / human / vehicle)",
        detect_classes=None,
        species=["animal (generic)", "human", "vehicle"],
        source="megadetector",
        auto_download=False,
        repo_id=None,
    ),
}

# ── COCO fallback models (ultralytics auto-downloads on first use) ─────────────

_BUILTIN_DEFS: list[tuple[str, str]] = [
    ("yolo26n", "YOLO26 Nano — COCO fallback, fastest"),
    ("yolo26s", "YOLO26 Small — COCO fallback (no wildlife-specific training)"),
    ("yolo26m", "YOLO26 Medium — COCO fallback, highest accuracy"),
    ("yolo26l", "YOLO26 Large — COCO fallback"),
    ("yolo26x", "YOLO26 Extra-Large — COCO fallback, maximum accuracy"),
]
_BUILTIN_NAMES: set[str] = {fname for fname, _ in _BUILTIN_DEFS}


# ── Public API ─────────────────────────────────────────────────────────────────

def list_models() -> list[ModelInfo]:
    """
    Returns:
      1. UWyo wildlife catalog (always listed; downloaded flag set per filesystem)
      2. Any other .pt / .onnx / .engine files found in models/
      3. COCO fallback models (ultralytics auto-download)
    """
    result: list[ModelInfo] = []

    # 1 — Wildlife catalog (always listed)
    for fname, tmpl in _WILDLIFE_CATALOG.items():
        abs_path = os.path.join(_MODELS_DIR, fname)
        exists   = os.path.isfile(abs_path)
        result.append(ModelInfo(
            name=tmpl.name,
            path=abs_path if exists else tmpl.path,
            description=tmpl.description,
            detect_classes=tmpl.detect_classes,
            species=tmpl.species,
            source=tmpl.source,
            auto_download=tmpl.auto_download,
            repo_id=tmpl.repo_id,
            hf_filename=tmpl.hf_filename,
            downloaded=exists,
        ))

    # 2 — Other custom files not in the catalog and not a builtin
    if os.path.isdir(_MODELS_DIR):
        for fname in sorted(os.listdir(_MODELS_DIR)):
            if not fname.endswith((".pt", ".onnx", ".engine")):
                continue
            stem = os.path.splitext(fname)[0]
            if fname in _WILDLIFE_CATALOG or stem in _BUILTIN_NAMES:
                continue
            abs_path = os.path.join(_MODELS_DIR, fname)
            result.append(ModelInfo(
                name=stem,
                path=abs_path,
                description=f"{stem} (custom)",
                source="custom",
                auto_download=False,
                downloaded=True,
            ))

    # 3 — COCO fallback models (use local copy if present, otherwise rely on ultralytics hub)
    for name, desc in _BUILTIN_DEFS:
        fname    = f"{name}.pt"
        abs_path = os.path.join(_MODELS_DIR, fname)
        exists   = os.path.isfile(abs_path)
        result.append(ModelInfo(
            name=name,
            path=abs_path if exists else fname,
            description=desc,
            detect_classes=_COCO_WILDLIFE,
            species=["bird", "bear", "horse", "sheep", "cow"],
            source="ultralytics",
            downloaded=exists,
        ))

    return result


def get_model(name: str) -> Optional[ModelInfo]:
    return next((m for m in list_models() if m.name == name), None)


def models_dir() -> str:
    os.makedirs(_MODELS_DIR, exist_ok=True)
    return _MODELS_DIR
