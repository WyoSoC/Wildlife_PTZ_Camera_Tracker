from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

from .config import TrackConfig, SpeedConfig


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

    def draw(self, img: np.ndarray, color: tuple = (0, 255, 0)) -> None:
        cv2.rectangle(img, (self.x1, self.y1), (self.x2, self.y2), color, 2)
        label = f"ID:{self.track_id}" if self.track_id is not None else f"{self.conf:.2f}"
        cv2.putText(
            img, label, (self.x1, max(0, self.y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
        )


class Detector:
    """
    YOLO detection + DeepSort multi-object tracking.

    update() returns (confirmed_tracks, raw_detections).
    Caller selects the primary target:
        primary = confirmed[0] if confirmed else (max(raw, key=...) if raw else None)
    """

    def __init__(self, cfg: TrackConfig) -> None:
        self._model = YOLO(cfg.model_path)
        # MPS on Apple Silicon, CUDA if available, else CPU
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        self._model.to(device)
        self._tracker = DeepSort(max_age=cfg.tracker_max_age)
        self._classes = cfg.detect_classes

    def update(
        self, frame: np.ndarray
    ) -> tuple[list[BBox], list[BBox]]:
        results = self._model(frame, classes=self._classes, verbose=False)[0]

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
            confirmed.append(
                BBox(lx1, ly1, lx2, ly2, track_id=t.track_id, confirmed=True)
            )

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
