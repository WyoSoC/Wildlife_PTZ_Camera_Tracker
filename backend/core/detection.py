from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

from .config import TrackConfig, DeviceConfig, SpeedConfig
from .device import select_device, half_supported, device_info

logger = logging.getLogger(__name__)


@dataclass
class BBox:
    x1: int
    y1: int
    x2: int
    y2: int
    conf: float = 0.0
    cls_name: str = ""
    track_id: Optional[int] = None
    confirmed: bool = False

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def width(self) -> int:
        return max(1, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(1, self.y2 - self.y1)

    @property
    def area(self) -> int:
        return self.width * self.height

    def draw(self, img: np.ndarray, color: tuple = (0, 255, 0), thickness: int = 2) -> None:
        cv2.rectangle(img, (self.x1, self.y1), (self.x2, self.y2), color, thickness)

        parts: list[str] = []
        if self.cls_name:
            parts.append(self.cls_name.replace('_', ' '))
        if self.conf > 0:
            parts.append(f"{self.conf * 100:.0f}%")
        if not parts and self.track_id is not None:
            parts.append(f"ID {self.track_id}")
        label = "  ".join(parts) if parts else "?"

        font_scale = 0.40 if thickness == 1 else 0.50
        cv2.putText(
            img, label, (self.x1, max(12, self.y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA,
        )


class Detector:
    """
    YOLO detection + DeepSort multi-object tracking.

    update() returns (confirmed_tracks, raw_detections).
    Caller selects the primary target:
        primary = confirmed[0] if confirmed else (max(raw, key=...) if raw else None)
    """

    def __init__(self, track_cfg: TrackConfig, dev_cfg: DeviceConfig = DeviceConfig()) -> None:
        self._device = select_device(dev_cfg.device)
        self._half   = dev_cfg.half and half_supported(self._device)

        model_path = track_cfg.model_path
        if not os.path.isfile(model_path) and "/" not in model_path and not model_path.startswith("yolo"):
            raise FileNotFoundError(
                f"Model file not found: '{model_path}'. "
                "Download it and place it in the models/ directory, or switch to an available model."
            )
        self._model = YOLO(model_path)
        self._model.to(self._device)

        info = device_info(self._device)
        logger.info(
            "Detector: %s | half=%s | model=%s",
            info.get("device_name", str(self._device)),
            self._half,
            track_cfg.model_path,
        )
        if info.get("vram_gb"):
            logger.info("  VRAM: %.1f GB  CUDA: %s  SM: %s",
                        info["vram_gb"], info.get("cuda_version", "?"),
                        info.get("sm_capability", "?"))

        # Warm-up: trigger CUDA JIT/kernel compilation on a dummy frame so the
        # first real camera frame doesn't pay the one-time compile cost.
        # half= must be passed here too — ultralytics predictor resets the model
        # dtype during its own setup step, so model.half() alone is not reliable.
        _dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        self._model(_dummy, verbose=False, half=self._half)
        logger.info("GPU warm-up complete")

        self._tracker = DeepSort(
            max_age=track_cfg.tracker_max_age,
            half=self._half,
            embedder_gpu=self._device.type != "cpu",
        )
        self._classes = track_cfg.detect_classes

    @property
    def device(self) -> torch.device:
        return self._device

    def update(
        self, frame: np.ndarray
    ) -> tuple[list[BBox], list[BBox]]:
        results = self._model(
            frame, classes=self._classes, verbose=False, half=self._half
        )[0]

        raw: list[BBox] = []
        ds_input: list = []
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            cls_id = int(box.cls[0].item()) if hasattr(box, "cls") else -1
            cls_name = self._model.names.get(cls_id, str(cls_id))
            raw.append(BBox(int(x1), int(y1), int(x2), int(y2), conf, cls_name))
            ds_input.append(([x1, y1, x2 - x1, y2 - y1], conf, cls_name))

        tracks = self._tracker.update_tracks(ds_input, frame=frame)
        confirmed: list[BBox] = []
        for t in tracks:
            if not t.is_confirmed():
                continue
            lx1, ly1, lx2, ly2 = map(int, t.to_ltrb())
            det_conf  = t.get_det_conf()
            det_class = t.get_det_class()
            confirmed.append(BBox(
                lx1, ly1, lx2, ly2,
                conf     = det_conf  if det_conf  is not None else 0.0,
                cls_name = det_class if det_class is not None else "",
                track_id = t.track_id,
                confirmed = True,
            ))

        return confirmed, raw


class SpeedEstimator:
    """
    ID-agnostic, EMA-smoothed speed from successive target bounding-box centres.
    Works across track ID switches because it only needs (cx, cy, t).
    """

    def __init__(self, cfg: SpeedConfig, frame_w: int) -> None:
        self._cfg = cfg
        self._deg_per_px = cfg.hfov_deg / max(1, float(frame_w))
        self._last: Optional[tuple[int, int, float]] = None
        self.speed_px: float = 0.0
        self.speed_deg: float = 0.0

    def update(self, cx: int, cy: int, now: float) -> tuple[float, float]:
        if self._last is not None:
            pcx, pcy, pt = self._last
            dt = max(1e-6, now - pt)
            if dt >= self._cfg.min_dt_sec:
                dist = ((cx - pcx) ** 2 + (cy - pcy) ** 2) ** 0.5
                sp_px = dist / dt
                sp_deg = dist * self._deg_per_px / dt
                a = self._cfg.smooth_alpha
                self.speed_px = a * sp_px + (1.0 - a) * self.speed_px
                self.speed_deg = a * sp_deg + (1.0 - a) * self.speed_deg
        self._last = (cx, cy, now)
        return self.speed_px, self.speed_deg

    def reset(self) -> None:
        self._last = None
        self.speed_px = 0.0
        self.speed_deg = 0.0
