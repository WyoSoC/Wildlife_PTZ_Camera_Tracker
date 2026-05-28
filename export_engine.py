#!/usr/bin/env python3
"""
Convert .pt YOLO models to TensorRT .engine for Jetson Orin inference.

Bypasses PyTorch's CUDA kernel path (which lacks SM 8.7 kernels in the cu126
wheel) by using the TRT Python API directly on the existing .onnx files.
The output is ultralytics-compatible: metadata JSON is prepended so
YOLO('model.engine') loads class names and end2end flag automatically.

Usage:
    .venv/bin/python export_engine.py              # convert all .pt in models/
    .venv/bin/python export_engine.py models/foo.pt [models/bar.pt ...]
    .venv/bin/python export_engine.py --imgsz 640 --fp32
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys


def _read_pt_metadata(pt_path: str) -> dict:
    """Extract class names and YAML config from a YOLO .pt checkpoint."""
    import torch
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    m = ckpt.get("model")
    if m is None:
        return {}
    names  = dict(m.names) if hasattr(m, "names") else {}
    yaml   = m.yaml if hasattr(m, "yaml") and isinstance(m.yaml, dict) else {}
    return {"names": names, "yaml": yaml}


def _build_engine_bytes(onnx_path: str, half: bool, workspace_gb: int) -> bytes:
    """Build a TRT serialised engine from an ONNX file.  No PyTorch kernels used."""
    import tensorrt as trt

    logger  = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser  = trt.OnnxParser(network, logger)

    with open(onnx_path, "rb") as f:
        raw = f.read()
    if not parser.parse(raw):
        errs = [str(parser.get_error(i)) for i in range(parser.num_errors)]
        raise RuntimeError("ONNX parse failed:\n" + "\n".join(errs))

    config = builder.create_builder_config()
    config.set_memory_pool_limit(
        trt.MemoryPoolType.WORKSPACE, workspace_gb << 30
    )
    if half:
        config.set_flag(trt.BuilderFlag.FP16)

    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT build_serialized_network returned None")
    return bytes(serialized)


def _make_ultralytics_engine(
    engine_bytes: bytes,
    names: dict,
    imgsz: int,
    half: bool,
    end2end: bool,
    batch: int = 1,
    stride: int = 32,
    channels: int = 3,
) -> bytes:
    """Prepend ultralytics metadata so YOLO('model.engine') works out of the box.

    Format: [4-byte LE meta_len][utf-8 JSON][engine_bytes]
    """
    meta = {
        "description": "Ultralytics YOLO TensorRT export",
        "author":      "export_engine.py",
        "stride":      str(stride),
        "task":        "detect",
        "batch":       str(batch),
        "imgsz":       str([imgsz, imgsz]),
        "names":       str(names),
        "channels":    str(channels),
        "end2end":     str(end2end),
        # Explicit task avoids ultralytics 'unable to guess task' warning at load time
        "args":        str({"task": "detect", "nms": end2end}),
    }
    meta_bytes = json.dumps(meta).encode("utf-8")
    meta_len   = len(meta_bytes).to_bytes(4, byteorder="little")
    return meta_len + meta_bytes + engine_bytes


def export_one(
    pt_path: str,
    imgsz: int,
    batch: int,
    half: bool,
    workspace_gb: int,
    force: bool,
) -> str:
    engine_path = os.path.splitext(pt_path)[0] + ".engine"
    onnx_path   = os.path.splitext(pt_path)[0] + ".onnx"

    if os.path.exists(engine_path) and not force:
        print(f"  [skip] {engine_path} already exists  (--force to rebuild)")
        return engine_path

    # ── Metadata from .pt ────────────────────────────────────────────────────
    print(f"  Reading metadata from {os.path.basename(pt_path)} ...")
    meta   = _read_pt_metadata(pt_path)
    names  = meta.get("names", {})
    end2end = meta.get("yaml", {}).get("end2end", False)
    print(f"    classes={len(names)}  end2end={end2end}")

    # ── ONNX source ───────────────────────────────────────────────────────────
    if not os.path.exists(onnx_path):
        raise FileNotFoundError(
            f"No matching .onnx found at {onnx_path}\n"
            "Export the .pt to ONNX first (on a machine with working CUDA kernels):\n"
            "  from ultralytics import YOLO; YOLO('model.pt').export(format='onnx')"
        )

    # ── TRT build ─────────────────────────────────────────────────────────────
    print(f"  Building TRT engine from {os.path.basename(onnx_path)} "
          f"(FP16={half}, workspace={workspace_gb}GB) ...")
    print("    This may take several minutes on first run (calibration + layer fusion).")
    engine_bytes = _build_engine_bytes(onnx_path, half=half, workspace_gb=workspace_gb)

    # ── Wrap with ultralytics metadata ────────────────────────────────────────
    payload = _make_ultralytics_engine(
        engine_bytes,
        names=names,
        imgsz=imgsz,
        half=half,
        end2end=end2end,
        batch=batch,
    )

    with open(engine_path, "wb") as f:
        f.write(payload)

    size_mb = os.path.getsize(engine_path) / 1e6
    print(f"  Saved → {engine_path}  ({size_mb:.1f} MB)")
    return engine_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("models", nargs="*", help=".pt paths (default: models/*.pt)")
    parser.add_argument("--imgsz",     type=int, default=640, help="Image size (default 640)")
    parser.add_argument("--batch",     type=int, default=1,   help="Batch size (default 1)")
    parser.add_argument("--workspace", type=int, default=4,   help="TRT workspace GB (default 4)")
    parser.add_argument("--fp32",      action="store_true",   help="Use FP32 instead of FP16")
    parser.add_argument("--force",     action="store_true",   help="Rebuild even if .engine exists")
    args = parser.parse_args()

    half = not args.fp32

    targets: list[str] = args.models
    if not targets:
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        targets = sorted(glob.glob(os.path.join(models_dir, "*.pt")))

    if not targets:
        print("No .pt files found. Pass paths or place .pt files in models/")
        sys.exit(1)

    print(f"\nConverting {len(targets)} model(s) → TensorRT .engine  "
          f"(FP16={half}, imgsz={args.imgsz})\n")

    ok, fail = 0, 0
    for pt in targets:
        print(f"[{os.path.basename(pt)}]")
        try:
            export_one(
                pt,
                imgsz=args.imgsz,
                batch=args.batch,
                half=half,
                workspace_gb=args.workspace,
                force=args.force,
            )
            ok += 1
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            fail += 1
        print()

    print(f"Done. {ok} succeeded, {fail} failed.")


if __name__ == "__main__":
    main()
