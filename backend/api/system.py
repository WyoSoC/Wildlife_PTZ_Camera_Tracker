"""
System performance metrics — CPU, memory, GPU (NVIDIA), power.
Also exposes NTP time-sync control.
"""
from __future__ import annotations
import asyncio
import logging
import os
import platform

from fastapi import APIRouter, HTTPException

from ..core.device import select_device, device_info
from ..core import time_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])

try:
    import psutil
    _PSUTIL = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    _PSUTIL = False

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML = True
except Exception:
    pynvml = None  # type: ignore[assignment]
    _NVML = False


def _jetson_gpu() -> dict | None:
    """Read Jetson integrated GPU metrics from sysfs (fallback when NVML unavailable)."""
    import glob
    # GPU load sysfs path differs by Jetson platform: Orin uses a bus-addressed path
    load_path: str | None = None
    for pattern in (
        '/sys/devices/gpu.0/load',
        '/sys/devices/platform/bus@0/*.gpu/load',
        '/sys/devices/platform/*/*.gpu/load',
        '/sys/devices/platform/*.gpu/load',
    ):
        matches = glob.glob(pattern)
        if matches:
            load_path = matches[0]
            break
    if load_path is None:
        return None
    try:
        load_pct = int(open(load_path).read().strip()) / 10.0
        temp_c: float | None = None
        thermal_base = '/sys/class/thermal'
        if os.path.isdir(thermal_base):
            for zone in sorted(os.listdir(thermal_base)):
                type_f = os.path.join(thermal_base, zone, 'type')
                temp_f = os.path.join(thermal_base, zone, 'temp')
                if os.path.exists(type_f) and os.path.exists(temp_f):
                    zone_type = open(type_f).read().strip().lower()
                    if 'gpu' in zone_type:
                        raw = open(temp_f).read().strip()
                        if raw:
                            temp_c = int(raw) / 1000.0
                        break

        gpu_name = 'NVIDIA Jetson (integrated GPU)'
        if _NVML:
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                n = pynvml.nvmlDeviceGetName(h)
                gpu_name = n.decode() if isinstance(n, bytes) else n
            except Exception:
                pass

        return {
            'name':             gpu_name,
            'utilization_pct':  round(load_pct, 1),
            'memory_used_gb':   None,
            'memory_total_gb':  None,
            'temperature_c':    temp_c,
            'power_watts':      None,
        }
    except Exception:
        return None


@router.get("/metrics")
async def get_metrics():
    """Live CPU, memory, and (if NVIDIA GPU present) GPU utilisation + power."""
    result: dict = {
        "cpu_percent": None,
        "memory":      {},
        "gpu":         None,
    }

    if _PSUTIL:
        result["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        result["memory"] = {
            "percent":  round(mem.percent, 1),
            "used_gb":  round(mem.used  / 1e9, 2),
            "total_gb": round(mem.total / 1e9, 2),
        }

    if _NVML:
        try:
            handle    = pynvml.nvmlDeviceGetHandleByIndex(0)
            util      = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info  = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp      = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            name_raw  = pynvml.nvmlDeviceGetName(handle)
            gpu_name  = name_raw.decode() if isinstance(name_raw, bytes) else name_raw
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                power_w  = round(power_mw / 1000, 1)
            except Exception:
                power_w = None
            result["gpu"] = {
                "name":              gpu_name,
                "utilization_pct":   util.gpu,
                "memory_used_gb":    round(mem_info.used  / 1e9, 2),
                "memory_total_gb":   round(mem_info.total / 1e9, 2),
                "temperature_c":     temp,
                "power_watts":       power_w,
            }
        except Exception as exc:
            logger.debug("NVML metrics error: %s", exc)

    if result["gpu"] is None:
        result["gpu"] = _jetson_gpu()

    return result


@router.get("/info")
async def get_info():
    """Static server platform info (device, VRAM, CUDA version, etc.)."""
    dev  = select_device()
    info = device_info(dev)
    return {
        "os":            platform.system(),
        "machine":       platform.machine(),
        "python":        platform.python_version(),
        "device":        str(dev),
        **info,
        "psutil":        _PSUTIL,
        "nvml":          _NVML,
    }


# ── NTP time sync ──────────────────────────────────────────────────────────────

@router.get("/ntp-status")
async def ntp_status():
    """Return the current NTP offset and last-sync metadata."""
    return time_sync.status()


@router.post("/ntp-sync")
async def ntp_sync():
    """Query NTP servers and update the UTC offset used for video timestamps."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, time_sync.sync)
        return result
    except Exception as exc:
        raise HTTPException(503, detail=str(exc))
