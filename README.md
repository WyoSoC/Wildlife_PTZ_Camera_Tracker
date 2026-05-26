# Eagle Tracker — Web App

Browser-based control panel for NDI PTZ cameras with YOLO auto-tracking.
Runs as a single Python server on a Mac Mini (Apple Silicon) on the camera LAN;
accessible from any browser via Tailscale.

---

## Architecture

```
Browser (any device, any OS)
  │  WebRTC video  ←─────────────────────────────────────────┐
  │  WebSocket (PTZ cmds / telemetry 10 Hz)  ←──────────────┐│
  │  REST /api/*  (config, recordings, camera control)       ││
  └──────────────────────────── HTTPS (Tailscale) ──────────▶││
                                                              ││
Mac Mini / MacBook (on camera LAN)                           ││
  ┌─ FastAPI (uvicorn :8080) ───────────────────────────────┐││
  │   api/cameras.py   — source discovery, start/stop loop  │││
  │   api/ptz.py       — WebSocket bridge                   │╔╝│
  │   api/webrtc.py    — SDP signaling + NDIVideoTrack      ╔╝ │
  │   api/recordings.py — file download                     │   │
  │                                                          │   │
  │  ┌─ daemon thread: TrackLoop ──────────────────────────┐│   │
  │  │  NDIReceiver / RtspCapture                          ││   │
  │  │  → Detector (YOLOv8 + DeepSort, MPS)               ││   │
  │  │  → PanController / ZoomController                  ││   │
  │  │  → VideoRecorder (CFR MP4)                         ││   │
  │  │  → session.push_frame(bgr)  ──────────────────────▶╝│   │
  │  └─────────────────────────────────────────────────────┘│   │
  │   core/session.py  — singleton, thread→asyncio bridge   │   │
  └──────────────────────────────────────────────────────────┘   │
        │  NDI SDK (native)                                       │
        └──────────── LAN ────────── BirdDog / Bolin NDI camera ──┘
```

### Key design decisions

| Concern | Choice | Reason |
|---|---|---|
| Video to browser | WebRTC (aiortc) | ~50–150 ms latency; no plugin required |
| Joystick | Web Gamepad API | Zero install, works with DualSense/Xbox in Chrome/Firefox/Safari |
| NDI capture | Server-side only | NDI SDK is a native library; cannot run in browser |
| Compute | Apple MPS backend | Runs YOLOv8 inference on the M-series GPU automatically |
| Remote access | Tailscale Serve | HTTPS without port forwarding; works across NAT |
| Packaging | PyInstaller `.app` | Single double-click binary; no Python install needed on server |

---

## Prerequisites

### Server (Mac Mini / MacBook)

- macOS 13+ on Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- [NDI Tools SDK](https://ndi.video/for-developers/ndi-sdk/) — install the Python wheel separately
- [Tailscale](https://tailscale.com/) (for remote HTTPS access)
- Node.js 20+ and npm (only needed to build the frontend; not required for production)

### Browser (client)

No installation. Chrome, Firefox, or Safari on any OS.
Use a USB or Bluetooth gamepad for joystick control (DualSense, Xbox, generic HID).

---

## Development Setup

### 1  Backend

Choose the requirements file for your hardware:

| Platform | Command |
|---|---|
| macOS (Apple Silicon, MPS) | `pip install -r requirements.txt` |
| Linux desktop/laptop NVIDIA GPU | `pip install -r requirements-cuda.txt` |
| Jetson Orin Nano (JetPack 6) | See `requirements-jetson.txt` for two-step install |

```bash
cd backend
python -m venv .venv && source .venv/bin/activate

# macOS:
pip install -r requirements.txt

# Linux NVIDIA (CUDA 12.4):
pip install -r requirements-cuda.txt

# Jetson Orin Nano (JetPack 6):
pip install torch torchvision --index-url https://pypi.jetson-ai-lab.dev/jp6/cu126
pip install -r requirements-jetson.txt

# Install NDI SDK wheel (path varies by SDK version):
# pip install /path/to/NDIlib-*.whl

uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

API is live at `http://localhost:8080`.
Interactive docs: `http://localhost:8080/docs`.

### 2  Frontend (dev server with hot-reload)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Vite proxies `/api` and `/ws` to `:8080`, so the backend must be running.

---

## Production Build

```bash
# 1. Build React → static files inside backend/static/
cd frontend
npm run build      # outputs to ../backend/static (see vite.config.ts)

# 2. Run the server (serves the SPA automatically)
cd ..
python -m backend.main
# or:  uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

The server opens `http://localhost:8080` in the default browser automatically.

---

## Inference Device

The server selects the inference device automatically on startup.
Priority order: **CUDA → MPS → CPU**.

| Hardware | Device string | Notes |
|---|---|---|
| NVIDIA desktop/laptop GPU | `cuda` or `cuda:0` | FP16 enabled by default (~2× speedup) |
| Jetson Orin Nano / NX / AGX | `cuda` | FP16 critical — 8 GB unified memory |
| Apple Silicon M-series | `mps` | FP16 disabled (model-dependent stability) |
| CPU fallback | `cpu` | Usable for testing; ~5–10× slower than GPU |

Override via `DeviceConfig` in session config (API: `PUT /api/cameras/config`),
or set it in a custom profile in `backend/core/config.py`:

```python
from backend.core.config import AppConfig, DeviceConfig

my_config = AppConfig(
    device=DeviceConfig(device="cuda:0", half=True),
    # ... other sub-configs
)
```

### TensorRT (Jetson — optional, 2–4× speedup)

Export the YOLO model to a TensorRT engine once, then pass the `.engine` file
as `model_path` in `TrackConfig`:

```bash
python - <<'EOF'
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.export(format="engine", half=True, device=0, imgsz=640)
# Produces yolov8n.engine
EOF
```

Then set `track.model_path = "yolov8n.engine"` in your profile or via the Camera
config API.

---

## Tailscale (Remote HTTPS Access)

```bash
# On the Mac Mini — run once after tailscale up:
tailscale serve https / http://localhost:8080
```

Your browser can then reach the app at `https://<machine-name>.tailXXXX.ts.net` from
any device on the same Tailscale network with no port forwarding.
WebRTC ICE negotiation works over Tailscale peer addresses automatically.

---

## REST API Reference

All endpoints are prefixed `/api/`.

### Cameras

| Method | Path | Description |
|---|---|---|
| `GET` | `/cameras/discover` | Scan LAN for NDI sources (~2 s) |
| `POST` | `/cameras/connect` | Set active source (`source_match`, `source_type`, `rtsp_url`) |
| `POST` | `/cameras/start` | Start background capture + tracking loop |
| `POST` | `/cameras/stop` | Stop the loop |
| `GET` | `/cameras/status` | `{connected, running, source_name, mode}` |
| `POST` | `/cameras/disconnect` | Alias for stop |
| `GET` | `/cameras/config` | Full `AppConfig` as JSON |
| `PUT` | `/cameras/config` | Partial update — any subset of config fields |
| `GET` | `/cameras/profiles` | List named profiles (`birddog`, `bolin`) |
| `POST` | `/cameras/profiles/{name}/load` | Replace active config with a named profile |

#### `PUT /cameras/config` fields

```json
{
  "pan_dead_zone_px": 40,
  "pan_thresh_px": 100,
  "pan_kp": 0.9,
  "pan_max_speed": 0.8,
  "pan_min_speed": 0.20,
  "pan_invert": true,
  "zoom_in_frac": 0.18,
  "zoom_out_frac": 0.40,
  "zoom_speed": 0.6,
  "zoom_invert": false,
  "zoom_ema_alpha": 0.45,
  "detect_classes": 0,
  "record_duration_sec": 40,
  "record_fps": 30,
  "hfov_deg": 60.0
}
```

All fields are optional — only supplied fields are updated.

### WebRTC

| Method | Path | Description |
|---|---|---|
| `POST` | `/webrtc/offer` | SDP offer/answer — browser sends its offer, receives the server answer |

### Recordings

| Method | Path | Description |
|---|---|---|
| `GET` | `/recordings` | List MP4 files in `videos/with_box/` |
| `GET` | `/recordings/{filename}` | Download / stream a recording |
| `GET` | `/logs` | List joystick CSV logs |
| `GET` | `/logs/{filename}` | Download a CSV log |

---

## WebSocket Protocol

**`ws://host/ws/ptz`** — bidirectional.

### Inbound (browser → server)

```jsonc
// Move camera
{"type": "pan_tilt", "pan": 0.5, "tilt": 0.0}   // -1.0 … 1.0
{"type": "zoom",     "speed": -0.3}               // -1.0 … 1.0

// Instant commands
{"type": "stop"}
{"type": "autofocus"}

// Mode switch
{"type": "mode", "mode": "manual"}       // "manual" | "auto_track"

// Recording
{"type": "record", "action": "start"}   // "start" | "stop"
```

### Outbound (server → browser, 10 Hz)

```jsonc
{
  "type": "telemetry",
  "connected": true,
  "source_name": "BIRDDOG-P200",
  "mode": "auto_track",
  "fps": 29.8,
  "detected": true,
  "track_id": 3,
  "confidence": 0.91,
  "speed_px": 12.4,
  "speed_deg": 8.2,
  "wfrac_ema": 0.22,
  "rec_active": false,
  "rec_elapsed": 0.0,
  "rec_total": 40.0
}
```

---

## Configuration Reference

### Pan controller

| Field | Default | Description |
|---|---|---|
| `dead_zone_px` | 40 | Pixels from center where pan is suppressed entirely |
| `thresh_px` | 100 | Pixels from center where full proportional gain kicks in |
| `kp` | 0.9 | Proportional gain (speed = kp × error / half_width) |
| `max_speed` | 0.8 | Hard cap on commanded pan speed (0–1) |
| `min_speed` | 0.20 | Minimum non-zero speed sent to camera |
| `invert` | true | Flip pan direction (needed for BirdDog) |

### Zoom controller

| Field | Default | Description |
|---|---|---|
| `zoom_in_frac` | 0.18 | Subject width fraction below which camera zooms in |
| `zoom_out_frac` | 0.40 | Subject width fraction above which camera zooms out |
| `speed` | 0.6 | Zoom command speed magnitude |
| `ema_alpha` | 0.45 | EMA smoothing on subject width (0 = very smooth, 1 = raw) |
| `invert` | false | Flip zoom direction |

### Named profiles

| Profile | Camera | Process res | Model | Record |
|---|---|---|---|---|
| `birddog` | BirdDog P200 | 480×288 | yolov8s.pt | 40 s @ 30 fps |
| `bolin` | Bolin PTZ | 720×488 | yolov8n.pt | 20 s @ 20 fps |

---

## Gamepad Mapping

Works with any W3C Gamepad API–compatible controller (DualSense, Xbox, generic HID).
Connect via USB or Bluetooth — the browser detects it automatically.

| Axis / Button | Control |
|---|---|
| Left stick X | Pan (inverted: push right → pan left) |
| Left stick Y | Tilt (inverted: push up → tilt down) |
| Right stick Y | Zoom (inverted: push up → zoom in) |
| Button 0 (✕ / A) | Stop all motion |
| Button 3 (△ / Y) | Trigger autofocus |

Axes are sent at 20 Hz and suppressed when mode is `auto_track`.
Deadzone: 0.1 (values below ignored).

---

## Project Layout

```
.
├── backend/
│   ├── core/
│   │   ├── config.py        # AppConfig dataclass hierarchy + named profiles
│   │   ├── ndi_io.py        # NDI source discovery + NDIReceiver capture
│   │   ├── ptz_cam.py       # NDIPTZCamera — pan/tilt/zoom/stop/autofocus
│   │   ├── detection.py     # Detector (YOLOv8+DeepSort), BBox, SpeedEstimator
│   │   ├── controllers.py   # PanController, ZoomController (EMA, rate-limiting)
│   │   ├── recorder.py      # VideoRecorder (CFR-paced MP4 output)
│   │   ├── hud.py           # draw_hud() overlay on frame
│   │   ├── session.py       # App-wide singleton; thread→asyncio frame bridge
│   │   └── track_loop.py    # TrackLoop daemon thread; RtspCapture
│   ├── api/
│   │   ├── cameras.py       # /api/cameras/* (discovery, connect, start, config)
│   │   ├── ptz.py           # ws://.../ws/ptz  (commands + telemetry)
│   │   ├── webrtc.py        # /api/webrtc/offer  (SDP exchange, NDIVideoTrack)
│   │   └── recordings.py    # /api/recordings/* + /api/logs/*
│   ├── main.py              # FastAPI app, lifespan, SPA fallback, entry point
│   └── requirements.txt
└── frontend/
    └── src/
        ├── api/client.ts    # Typed fetch wrappers for all REST endpoints
        ├── types/index.ts   # Shared TypeScript interfaces
        ├── hooks/
        │   ├── useWebSocket.ts  # Auto-reconnecting WS; exposes sendPanTilt etc.
        │   ├── useWebRTC.ts     # RTCPeerConnection lifecycle; returns stream
        │   └── useGamepad.ts    # rAF-based Gamepad API polling; deadzone
        ├── tabs/
        │   ├── CameraTab.tsx    # Source discovery, connect, config sliders
        │   ├── ControlTab.tsx   # Live video, joystick status, mode, recording
        │   └── LogsTab.tsx      # Recordings browser + inline player, CSV logs
        └── App.tsx              # Tab shell; single WS instance shared to tabs
├── archive/
│   ├── ndi_det.py               # Original YOLO+DeepSort pan+zoom script
│   ├── ndi_det_zoom.py          # Enhanced: multi-class, speed estimation
│   ├── ndi_joystick_log_ms.py   # Manual joystick PTZ with CSV logging
│   └── README.md                # Original project notes
└── README.md                    # This file
```
