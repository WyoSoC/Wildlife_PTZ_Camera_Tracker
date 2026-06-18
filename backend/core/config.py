from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CameraConfig:
    source_match: str = "birddog"
    ndi_timeout_ms: int = 50
    reolink_rtsp_url: str = ""          # non-empty → use RTSP instead of NDI


@dataclass
class VideoConfig:
    process_res: tuple[int, int] = (720, 480)


@dataclass
class TrackConfig:
    detect_classes: Optional[int] = None  # None = all model classes
    model_path: str = "yolo26s.pt"
    tracker_max_age: int = 30


@dataclass
class PanConfig:
    dead_zone_px: int = 40
    thresh_px: int = 100
    kp: float = 0.9
    max_speed: float = 0.8
    min_speed: float = 0.20
    invert: bool = True


@dataclass
class ZoomConfig:
    zoom_in_frac: float = 0.18
    zoom_out_frac: float = 0.40
    speed: float = 0.6
    invert: bool = False
    ema_alpha: float = 0.45


@dataclass
class CommandConfig:
    eps: float = 0.05
    min_interval_sec: float = 0.05
    no_track_stop_sec: float = 0.3


@dataclass
class RecordConfig:
    duration_sec: float = 40.0
    fps: int = 30
    record_res: tuple[int, int] = (1920, 1080)
    output_dir: str = "videos/with_box"


@dataclass
class SpeedConfig:
    enabled: bool = True
    hfov_deg: float = 60.0
    smooth_alpha: float = 0.5
    min_dt_sec: float = 0.050


@dataclass
class DeviceConfig:
    # "auto" selects CUDA → MPS → CPU in priority order.
    # Override with "cuda", "cuda:0", "cuda:1", "mps", or "cpu".
    device: str = "auto"
    # FP16 inference — automatically disabled on non-CUDA backends.
    # Gives ~2× speedup on NVIDIA GPUs and is critical on Jetson (unified memory).
    half: bool = True


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    track: TrackConfig = field(default_factory=TrackConfig)
    pan: PanConfig = field(default_factory=PanConfig)
    zoom: ZoomConfig = field(default_factory=ZoomConfig)
    command: CommandConfig = field(default_factory=CommandConfig)
    record: RecordConfig = field(default_factory=RecordConfig)
    speed: SpeedConfig = field(default_factory=SpeedConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)


# ── Named profiles ─────────────────────────────────────────────────────────────

BIRDDOG = AppConfig(
    camera=CameraConfig(source_match="birddog"),
    video=VideoConfig(process_res=(480, 288)),
    track=TrackConfig(model_path="yolo26s.pt"),
    record=RecordConfig(duration_sec=40, fps=30, record_res=(1920, 1080)),
)

BOLIN = AppConfig(
    camera=CameraConfig(source_match="bolin"),
    video=VideoConfig(process_res=(720, 488)),
    track=TrackConfig(model_path="yolo26n.pt"),
    record=RecordConfig(duration_sec=20, fps=20, record_res=(1280, 720)),
)

PROFILES: dict[str, AppConfig] = {
    "birddog": BIRDDOG,
    "bolin": BOLIN,
}
