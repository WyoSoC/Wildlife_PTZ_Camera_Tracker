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
    detect_classes:  Optional[int] = None  # None = all model classes
    model_path:      str           = "yolo26s.pt"
    tracker_max_age: int           = 30
    lock_confidence: float         = 0.50  # min detection confidence to lock onto a target


@dataclass
class PanConfig:
    dead_zone_px: int   = 40    # pixels from centre — no movement inside this band
    kp:           float = 0.9   # proportional gain (higher = more aggressive)
    max_speed:    float = 0.8   # max PTZ pan speed (0–1)
    min_speed:    float = 0.20  # floor to overcome motor stiction
    invert:       bool  = False  # flip pan direction — set True in camera-specific profiles


@dataclass
class ZoomConfig:
    zoom_in_frac:  float = 0.18  # zoom in when bbox < this fraction of frame width
    zoom_out_frac: float = 0.40  # zoom out when bbox > this fraction of frame width
    speed:         float = 0.6   # zoom motor speed (0–1)
    invert:        bool  = False  # flip zoom direction — set True in camera-specific profiles
    ema_alpha:     float = 0.45  # smoothing (0=no update, 1=no smoothing)


@dataclass
class CommandConfig:
    eps:               float = 0.05  # dead-band on speed delta — suppresses redundant commands
    min_interval_sec:  float = 0.05  # rate-limit: minimum time between PTZ commands
    no_track_stop_sec: float = 0.3   # stop motors this long after last detection
    lock_off_sec:      float = 3.0   # seconds after losing lock before resuming scan/idle


@dataclass
class RecordConfig:
    duration_sec: float = 30.0
    fps: int = 30
    record_res: tuple[int, int] = (1920, 1080)
    output_dir: str = "videos/with_box"


@dataclass
class SpeedConfig:
    enabled: bool = True
    hfov_deg: float = 60.0     # horizontal field of view (degrees) — affects speed readout
    smooth_alpha: float = 0.5
    min_dt_sec: float = 0.050


@dataclass
class DeviceConfig:
    device: str = "auto"       # "auto" | "cuda" | "cuda:0" | "mps" | "cpu"
    half:   bool = True        # FP16 inference (automatic fallback on non-CUDA)


# ── New: Home / Area / Scan ────────────────────────────────────────────────────

@dataclass
class HomeConfig:
    """Absolute PTZ position the camera returns to when not tracking."""
    pan:    float = 0.0    # -1.0 (left) to 1.0 (right)
    tilt:   float = 0.0   # -1.0 (down) to 1.0 (up)
    zoom:   float = 0.3   # 0.0 (wide) to 1.0 (tele)
    is_set: bool  = False  # False until user explicitly saves a home position


@dataclass
class AreaConfig:
    """
    Rectangular PTZ region for scan sweeping and (optionally) follow clamping.
    All coordinates in the same -1.0 to 1.0 space as PTZ speed/position commands.
    """
    enabled:   bool  = False
    pan_min:   float = -0.8
    pan_max:   float = 0.8
    tilt_min:  float = -0.4
    tilt_max:  float = 0.4
    scan_zoom: float = 0.3   # zoom level held during scanning


@dataclass
class ScanConfig:
    """
    Boustrophedon (lawnmower) sweep of the AreaConfig rectangle.
    The camera moves to each grid position, waits travel_sec for it to arrive,
    then observes for dwell_sec before advancing to the next position.
    """
    enabled:    bool  = False
    rows:       int   = 3      # tilt rows in the sweep grid
    cols:       int   = 5      # pan columns per row
    travel_sec: float = 3.0   # time allowed for camera to reach each position
    dwell_sec:  float = 3.0   # observation time at each position


@dataclass
class AppConfig:
    camera:  CameraConfig  = field(default_factory=CameraConfig)
    video:   VideoConfig   = field(default_factory=VideoConfig)
    track:   TrackConfig   = field(default_factory=TrackConfig)
    pan:     PanConfig     = field(default_factory=PanConfig)
    zoom:    ZoomConfig    = field(default_factory=ZoomConfig)
    command: CommandConfig = field(default_factory=CommandConfig)
    record:  RecordConfig  = field(default_factory=RecordConfig)
    speed:   SpeedConfig   = field(default_factory=SpeedConfig)
    device:  DeviceConfig  = field(default_factory=DeviceConfig)
    home:    HomeConfig    = field(default_factory=HomeConfig)
    area:    AreaConfig    = field(default_factory=AreaConfig)
    scan:    ScanConfig    = field(default_factory=ScanConfig)


# ── Named profiles ─────────────────────────────────────────────────────────────

BIRDDOG = AppConfig(
    camera=CameraConfig(source_match="birddog"),
    video=VideoConfig(process_res=(480, 288)),
    track=TrackConfig(model_path="yolo26s.pt"),
    pan=PanConfig(invert=True),   # BirdDog NDI pan axis is inverted relative to PTZ commands
    record=RecordConfig(duration_sec=30, fps=30, record_res=(1920, 1080)),
)

BOLIN = AppConfig(
    camera=CameraConfig(source_match="bolin"),
    video=VideoConfig(process_res=(720, 488)),
    track=TrackConfig(model_path="yolo26n.pt"),
    record=RecordConfig(duration_sec=20, fps=20, record_res=(1280, 720)),
)

PROFILES: dict[str, AppConfig] = {
    "birddog": BIRDDOG,
    "bolin":   BOLIN,
}
