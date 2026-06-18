"""
Wildlife model registry.

Subfolder layout under models/:
  general/      — multi-species models (north_american_wildlife, megadetector_v5)
  specialized/  — single-species UWyo fine-tuned models (26 species)
  coco/         — YOLO26 COCO baseline models (ultralytics auto-download)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional

_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models",
)

HF_ORG  = "UWyo"
HF_DATE = "2026-05-28"

# COCO class IDs for wildlife-adjacent categories
_COCO_WILDLIFE = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]


def _hf_fn(slug: str) -> str:
    return f"yolo26s_finetuned_{slug}_by_J.Gong_uwyo_{HF_DATE}.pt"


@dataclass
class ModelInfo:
    name:           str
    path:           str                        # value passed to YOLO()
    description:    str
    subdir:         str = ""                   # "general" | "specialized" | "coco" | ""
    detect_classes: Optional[list[int]] = None
    species:        list[str] = field(default_factory=list)
    source:         str = "ultralytics"        # "general" | "specialized" | "megadetector" | "ultralytics" | "custom"
    auto_download:  bool = True
    repo_id:        Optional[str] = None
    hf_filename:    str = "best.pt"
    download_url:   Optional[str] = None
    source_url:     Optional[str] = None       # any canonical source link (GitHub, HF, etc.)
    downloaded:     bool = True


# ── General multi-species models ───────────────────────────────────────────────

_GENERAL_CATALOG: list[ModelInfo] = [
    ModelInfo(
        name="north_american_wildlife",
        path="north_american_wildlife.pt",
        description="North American Wildlife — 26 classes, YOLO26s fine-tuned (UWyo)",
        subdir="general",
        detect_classes=None,
        species=[
            "badger", "bald eagle", "beaver", "bighorn sheep", "bison",
            "black bear", "bobcat", "coyote", "elk", "golden eagle",
            "gray wolf", "grizzly bear", "jackrabbit", "moose", "mountain lion",
            "mule deer", "osprey", "pika", "prairie dog", "pronghorn",
            "raven", "red-tailed hawk", "river otter", "sage grouse",
            "swift fox", "trumpeter swan",
        ],
        source="general",
        auto_download=True,
        repo_id=f"{HF_ORG}/wildlife-north-american-wildlife",
        hf_filename=_hf_fn("26-wildlife-class"),
    ),
    ModelInfo(
        name="megadetector_larch",
        path="megadetector_larch.pt",
        description="MegaDetector v1000-larch — YOLOv11L camera-trap detector (animal / person / vehicle)",
        subdir="general",
        detect_classes=None,
        species=["animal (generic)", "person", "vehicle"],
        source="megadetector",
        auto_download=True,
        source_url="https://github.com/agentmorris/MegaDetector/releases/tag/v1000.0",
        download_url="https://github.com/agentmorris/MegaDetector/releases/download/v1000.0/md_v1000.0.0-larch.pt",
    ),
    ModelInfo(
        name="megadetector_sorrel",
        path="megadetector_sorrel.pt",
        description="MegaDetector v1000-sorrel — YOLOv11s camera-trap detector, faster (animal / person / vehicle)",
        subdir="general",
        detect_classes=None,
        species=["animal (generic)", "person", "vehicle"],
        source="megadetector",
        auto_download=True,
        source_url="https://github.com/agentmorris/MegaDetector/releases/tag/v1000.0",
        download_url="https://github.com/agentmorris/MegaDetector/releases/download/v1000.0/md_v1000.0.0-sorrel.pt",
    ),
]


# ── Specialized single-species UWyo models ─────────────────────────────────────

def _uwyo(slug: str, display: str) -> ModelInfo:
    name = slug
    repo = f"{HF_ORG}/wildlife-{slug.replace('_', '-')}"
    return ModelInfo(
        name=name,
        path=f"{name}.pt",
        description=f"{display} — YOLO26s fine-tuned (UWyo)",
        subdir="specialized",
        detect_classes=None,
        species=[display.lower()],
        source="specialized",
        auto_download=True,
        repo_id=repo,
        hf_filename=_hf_fn(slug),
    )


_SPECIALIZED_CATALOG: list[ModelInfo] = [
    _uwyo("badger",          "Badger"),
    _uwyo("bald_eagle",      "Bald Eagle"),
    _uwyo("beaver",          "Beaver"),
    _uwyo("bighorn_sheep",   "Bighorn Sheep"),
    _uwyo("bison",           "Bison"),
    _uwyo("black_bear",      "Black Bear"),
    _uwyo("bobcat",          "Bobcat"),
    _uwyo("coyote",          "Coyote"),
    _uwyo("elk",             "Elk"),
    _uwyo("golden_eagle",    "Golden Eagle"),
    _uwyo("gray_wolf",       "Gray Wolf"),
    _uwyo("grizzly_bear",    "Grizzly Bear"),
    _uwyo("jackrabbit",      "Jackrabbit"),
    _uwyo("moose",           "Moose"),
    _uwyo("mountain_lion",   "Mountain Lion"),
    _uwyo("mule_deer",       "Mule Deer"),
    _uwyo("osprey",          "Osprey"),
    _uwyo("pika",            "Pika"),
    _uwyo("prairie_dog",     "Prairie Dog"),
    _uwyo("pronghorn",       "Pronghorn"),
    _uwyo("raven",           "Raven"),
    _uwyo("red_tailed_hawk", "Red-tailed Hawk"),
    _uwyo("river_otter",     "River Otter"),
    _uwyo("sage_grouse",     "Sage Grouse"),
    _uwyo("swift_fox",       "Swift Fox"),
    _uwyo("trumpeter_swan",  "Trumpeter Swan"),
]


# ── COCO fallback models (ultralytics auto-downloads on first use) ─────────────

_COCO_DEFS: list[tuple[str, str]] = [
    ("yolo26n", "YOLO26 Nano — COCO baseline, fastest"),
    ("yolo26s", "YOLO26 Small — COCO baseline"),
    ("yolo26m", "YOLO26 Medium — COCO baseline"),
    ("yolo26l", "YOLO26 Large — COCO baseline"),
    ("yolo26x", "YOLO26 Extra-Large — COCO baseline, most accurate"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _subdir_abs(subdir: str) -> str:
    return os.path.join(_MODELS_DIR, subdir) if subdir else _MODELS_DIR


def _resolve(tmpl: ModelInfo) -> ModelInfo:
    """Return a copy of tmpl with path and downloaded set from filesystem."""
    target_dir = _subdir_abs(tmpl.subdir)
    abs_path   = os.path.join(target_dir, f"{tmpl.name}.pt")
    exists     = os.path.isfile(abs_path)
    return ModelInfo(
        name=tmpl.name,
        path=abs_path if exists else f"{tmpl.name}.pt",
        description=tmpl.description,
        subdir=tmpl.subdir,
        detect_classes=tmpl.detect_classes,
        species=tmpl.species,
        source=tmpl.source,
        auto_download=tmpl.auto_download,
        repo_id=tmpl.repo_id,
        hf_filename=tmpl.hf_filename,
        download_url=tmpl.download_url,
        downloaded=exists,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def list_models() -> list[ModelInfo]:
    result: list[ModelInfo] = []

    known: set[str] = (
        {m.name for m in _GENERAL_CATALOG}
        | {m.name for m in _SPECIALIZED_CATALOG}
        | {name for name, _ in _COCO_DEFS}
    )

    # 1 — General multi-species
    for tmpl in _GENERAL_CATALOG:
        result.append(_resolve(tmpl))

    # 2 — Specialized single-species
    for tmpl in _SPECIALIZED_CATALOG:
        result.append(_resolve(tmpl))

    # 3 — Custom .pt files not in any catalog
    for root, dirs, files in os.walk(_MODELS_DIR):
        # skip hidden dirs (.cache etc.)
        dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
        rel = os.path.relpath(root, _MODELS_DIR)
        subdir = "" if rel == "." else rel
        for fname in sorted(files):
            if not fname.endswith((".pt", ".onnx", ".engine")):
                continue
            stem = os.path.splitext(fname)[0]
            if stem in known:
                continue
            abs_path = os.path.join(root, fname)
            result.append(ModelInfo(
                name=stem,
                path=abs_path,
                description=f"{stem} (custom)",
                subdir=subdir,
                source="custom",
                auto_download=False,
                downloaded=True,
            ))

    # 4 — COCO fallback models
    for name, desc in _COCO_DEFS:
        abs_path = os.path.join(_subdir_abs("coco"), f"{name}.pt")
        exists   = os.path.isfile(abs_path)
        result.append(ModelInfo(
            name=name,
            path=abs_path if exists else f"{name}.pt",
            description=desc,
            subdir="coco",
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
