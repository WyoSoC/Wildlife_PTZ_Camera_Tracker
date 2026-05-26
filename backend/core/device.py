"""
Device selection and introspection for PyTorch inference.

Priority (auto): CUDA → MPS → CPU

Jetson note: torch.cuda.is_available() returns True on JetPack 5/6, so Orin
Nano is handled automatically as long as the JetPack-distributed torch wheel
is installed (not the generic pip wheel).
"""
from __future__ import annotations
import logging

import torch

logger = logging.getLogger(__name__)


def select_device(prefer: str = "auto") -> torch.device:
    """
    Resolve *prefer* to a concrete torch.device, falling back gracefully.

    Args:
        prefer: "auto" | "cuda" | "cuda:N" | "mps" | "cpu"

    Returns:
        torch.device — guaranteed to be usable on this machine.
    """
    if prefer == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    if prefer.startswith("cuda"):
        if torch.cuda.is_available():
            return torch.device(prefer)
        logger.warning("CUDA requested but not available — falling back to CPU")
        return torch.device("cpu")

    if prefer == "mps":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        logger.warning("MPS requested but not available — falling back to CPU")
        return torch.device("cpu")

    return torch.device("cpu")


def half_supported(device: torch.device) -> bool:
    """FP16 is reliable on CUDA; MPS support is model-dependent; CPU doesn't support it."""
    return device.type == "cuda"


def device_info(device: torch.device) -> dict:
    """Return a serialisable dict describing the active inference device."""
    info: dict = {"device": str(device)}

    if device.type == "cuda":
        idx = device.index if device.index is not None else 0
        props = torch.cuda.get_device_properties(idx)
        info["device_name"]     = props.name
        info["vram_gb"]         = round(props.total_memory / 1e9, 1)
        info["cuda_version"]    = torch.version.cuda or ""
        info["sm_capability"]   = f"{props.major}.{props.minor}"
        # Jetson unified-memory devices report total_memory == system RAM
        info["is_jetson"]       = props.name.lower().startswith("orin") or \
                                   "jetson" in props.name.lower()
    elif device.type == "mps":
        info["device_name"] = "Apple Silicon GPU (MPS)"
    else:
        info["device_name"] = "CPU"

    return info
