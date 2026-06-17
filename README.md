# Wildlife PTZ Camera Tracker

Browser-based control panel for tracking wildlife with NDI PTZ cameras and YOLO inference.
Runs as a single Python server on an edge computer (Raspberry Pi, NVIDIA Jetson,
Mac Mini, or any Linux/macOS host) co-located on the camera LAN; accessible from
any browser via Tailscale.

**Live web app (GitHub Pages):** https://WyoSoC.github.io/Wildlife_PTZ_Camera_Tracker/

> The web app is a standalone frontend — enter your server's Tailscale URL on the
> connect screen to link it to your edge server.

**Repository:** https://github.com/WyoSoC/Wildlife_PTZ_Camera_Tracker

---

## Architecture

```
Browser (any device, any OS)
  │  WebRTC video  ←─────────────────────────────────────────┐
  │  WebSocket (PTZ cmds / telemetry 10 Hz)  ←──────────────┐│
  │  REST /api/*  (config, recordings, camera control)       ││
  └──────────────────────────── HTTPS (Tailscale) ──────────▶││
                                                              ││
Edge server (on camera LAN)                                  ││
  Raspberry Pi 5 · Jetson Orin · Mac Mini · Linux PC         ││
  ┌─ FastAPI (uvicorn :8080) ───────────────────────────────┐││
  │   api/cameras.py   — source discovery, start/stop loop  │││
  │   api/ptz.py       — WebSocket bridge                   │╔╝│
  │   api/webrtc.py    — SDP signaling + NDIVideoTrack      ╔╝ │
  │   api/recordings.py — file download                     │   │
  │                                                          │   │
  │  ┌─ daemon thread: TrackLoop ──────────────────────────┐│   │
  │  │  NDIReceiver / RtspCapture                          ││   │
  │  │  → Detector (YOLOv8 + DeepSort)                    ││   │
  │  │      CUDA (Jetson / NVIDIA GPU)                     ││   │
  │  │      MPS  (Apple Silicon)                           ││   │
  │  │      CPU  (Raspberry Pi / fallback)                 ││   │
  │  │  → PanController / ZoomController                  ││   │
  │  │  → VideoRecorder (CFR MP4)                         ││   │
  │  │  → session.push_frame(bgr)  ──────────────────────▶╝│   │
  │  └─────────────────────────────────────────────────────┘│   │
  │   core/session.py  — singleton, thread→asyncio bridge   │   │
  └──────────────────────────────────────────────────────────┘   │
        │  NDI SDK (native)                                       │
        └──────────── LAN ────── BirdDog / Bolin NDI / Reolink ──┘
```

### Key design decisions

| Concern | Choice | Reason |
|---|---|---|
| Video to browser | WebRTC (aiortc) | ~50–150 ms latency; no plugin required |
| Joystick | Web Gamepad API | Zero install, works with DualSense/Xbox in Chrome/Firefox/Safari |
| NDI capture | Server-side only | NDI SDK is a native library; cannot run in browser |
| Inference | CUDA / MPS / CPU auto-select | Same codebase runs on Jetson, Apple Silicon, Raspberry Pi |
| Remote access | Tailscale Serve | HTTPS without port forwarding; works across NAT |
| Packaging | PyInstaller binary | Single executable; no Python install needed on the edge server |

---

## Supported Edge Servers

| Hardware | OS | Inference | Notes |
|---|---|---|---|
| **NVIDIA Jetson Orin Nano/NX/AGX** | Ubuntu (JetPack 6) | CUDA (FP16) | Best performance/watt for edge deployment |
| **NVIDIA desktop / laptop GPU** | Linux / Windows WSL | CUDA (FP16) | RTX 3000+ recommended for real-time YOLO |
| **Apple Mac Mini / MacBook** | macOS 13+ (Apple Silicon) | MPS | Good throughput; NDI ecosystem well-supported on macOS |
| **Raspberry Pi 5** | Raspberry OS (64-bit) | CPU | Sufficient for lower-res streams; no GPU inference |
| **Any x86 Linux host** | Ubuntu 22.04+ | CUDA or CPU | Generic fallback for lab/bench setups |

NDI SDK is optional — the server starts without it and supports Reolink RTSP cameras on all platforms.

---

## Prerequisites

### Edge server

- Python 3.11+
- [NDI Tools SDK](https://ndi.video/for-developers/ndi-sdk/) wheel *(optional — required only for NDI cameras)*
- [Tailscale](https://tailscale.com/) *(for remote HTTPS access)*
- Node.js 20+ and npm *(build-time only — not needed at runtime)*

**Ubuntu 22.04 quick-start** (if Python 3.11 or Node.js are not already installed):

```bash
# Python 3.11 + venv
sudo apt install python3.11 python3.11-venv

# Node.js 20+ via NodeSource (the Ubuntu default is too old)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs
```

Platform-specific GPU prerequisites:

| Platform | Prerequisite |
|---|---|
| Jetson (JetPack 6) | JetPack installs CUDA, cuDNN automatically |
| NVIDIA Linux | [CUDA Toolkit 12.x](https://developer.nvidia.com/cuda-downloads) + driver ≥ 525 |
| Apple Silicon | No extra install — MPS ships with macOS + PyTorch |
| Raspberry Pi / CPU | No GPU prerequisite |

### Browser (client)

No installation required. Chrome, Firefox, or Safari on any OS.
Use a USB or Bluetooth gamepad for joystick control (DualSense, Xbox, generic HID).

---

## Development Setup

### 1  Backend

`install.py` auto-detects the platform (Jetson, NVIDIA GPU, macOS, Raspberry Pi,
or CPU), installs the correct PyTorch variant, then installs all remaining
dependencies from `requirements.txt`.

```bash
# Run from the project root (the directory that contains backend/ and frontend/)
python3.11 -m venv .venv && source .venv/bin/activate

cd backend
python install.py          # detects platform and installs everything

# Optional: NDI cameras (BirdDog, Bolin) — install the NDI Tools SDK wheel:
# pip install /path/to/NDIlib-*.whl

cd ..
python run_server.py --dev        # starts uvicorn with auto-reload
```

> **Note:** use `python3.11` (or whichever `python3.x` you installed) to create the
> venv — `python` is not available by default on Ubuntu.

To preview what will be installed without running anything:

```bash
cd backend
python install.py --dry-run   # print commands only
python install.py --list      # show detected platform and exit
```

API is live at `http://localhost:8080`.
Interactive docs: `http://localhost:8080/docs`.

> **Important:** always start the server from the project root using `python run_server.py`.
> Running `uvicorn backend.main:app` directly from inside the `backend/` directory
> will fail with `ModuleNotFoundError: No module named 'backend'` because Python
> needs the parent directory on `sys.path` to resolve the `backend` package.

### 2  Frontend (dev server with hot-reload)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Vite proxies `/api` and `/ws` to `:8080`, so the backend must be running first.

> **Security note:** run `npm audit fix` after install to pull in patched dependencies.
> If it reports breaking-change upgrades (e.g. a major Vite bump), use `npm audit fix --force`
> and verify the build still passes with `npm run build`.

---

## Production Build

```bash
# 1. Build React → static files inside backend/static/
cd frontend
npm run build      # outputs to ../backend/static (see vite.config.ts)

# 2. Run the server from the project root (serves the SPA automatically)
cd ..
python run_server.py                  # default: 0.0.0.0:8080
python run_server.py --port 9090      # custom port
```

> **Important:** always build the frontend **before** starting the server.
> The SPA route is only registered at startup when `backend/static/` exists.
> If you start the server first and build later, requests to `/` return 404 until
> the server is restarted.

---

## Inference Device

The server selects the inference device automatically on startup.
Priority order: **CUDA → MPS → CPU**.

| Hardware | Device string | Notes |
|---|---|---|
| NVIDIA desktop/laptop GPU | `cuda` or `cuda:0` | FP16 enabled by default (~2× speedup) |
| Jetson Orin Nano / NX / AGX | `cuda` | FP16 critical — unified memory shared with CPU |
| Apple Silicon M-series | `mps` | FP16 disabled (model-dependent stability) |
| Raspberry Pi / CPU fallback | `cpu` | Use `yolov8n.pt`; expect ~3–8 fps at 480×288 |

Override via `DeviceConfig` in a custom profile (`backend/core/config.py`):

```python
from backend.core.config import AppConfig, DeviceConfig

my_config = AppConfig(
    device=DeviceConfig(device="cuda:0", half=True),
)
```

### TensorRT (Jetson — optional, 2–4× additional speedup)

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

Then set `track.model_path = "yolov8n.engine"` in your profile or via `PUT /api/cameras/{camera_id}/config`.

---

## Tailscale (Remote HTTPS Access)

```bash
# Run once on the edge server after `tailscale up`:
tailscale serve https / http://localhost:8080
```

Your browser can then reach the app at `https://<machine-name>.tailXXXX.ts.net` from
any device on the same Tailscale network with no port forwarding or firewall rules.
WebRTC ICE negotiation works over Tailscale peer addresses automatically.

---

## REST API Reference

All endpoints are prefixed `/api/`. Interactive docs are available at
`http://localhost:8080/docs` when the server is running.

A default camera named `cam-1` is created automatically at startup.
Use it immediately, or create additional cameras with `POST /api/cameras`.

### Camera management

| Method | Path | Description |
|---|---|---|
| `GET` | `/cameras` | List all cameras and their status |
| `POST` | `/cameras` | Create a camera (`camera_id?`, `profile?`) |
| `DELETE` | `/cameras/{camera_id}` | Remove a camera |
| `GET` | `/cameras/discover` | Scan LAN for NDI sources (~2 s) |
| `GET` | `/cameras/profiles` | List named profiles (`birddog`, `bolin`) |

### Per-camera control

| Method | Path | Description |
|---|---|---|
| `POST` | `/cameras/{camera_id}/connect` | Set source (`source_match`, `source_type`, `rtsp_url?`) |
| `POST` | `/cameras/{camera_id}/start` | Start background capture + tracking loop |
| `POST` | `/cameras/{camera_id}/stop` | Stop the loop |
| `GET` | `/cameras/{camera_id}/status` | `{connected, running, source_name, mode, device, device_name}` |
| `GET` | `/cameras/{camera_id}/config` | Full config as JSON |
| `PUT` | `/cameras/{camera_id}/config` | Partial update — any subset of config fields |
| `POST` | `/cameras/{camera_id}/model` | Switch inference model by name |
| `POST` | `/cameras/{camera_id}/profiles/{name}/load` | Replace config with a named profile |

#### `PUT /cameras/{camera_id}/config` fields

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
  "hfov_deg": 60.0,
  "model_path": "yolov8s.pt"
}
```

All fields are optional — only supplied fields are updated.

### WebRTC

| Method | Path | Description |
|---|---|---|
| `POST` | `/webrtc/{camera_id}/offer` | SDP offer/answer — browser sends its offer, receives the server answer |

### Recordings

| Method | Path | Description |
|---|---|---|
| `GET` | `/recordings` | List MP4 files |
| `GET` | `/recordings/{filename}` | Download / stream a recording |
| `GET` | `/logs` | List joystick CSV logs |
| `GET` | `/logs/{filename}` | Download a CSV log |

### Models

| Method | Path | Description |
|---|---|---|
| `GET` | `/models` | List built-in and custom models with metadata |

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/system/info` | Static platform info: OS, device name, VRAM, CUDA version |
| `GET` | `/system/metrics` | Live CPU %, memory, GPU utilisation, temperature, power |

---

## WebSocket Protocol

**`ws://host/ws/ptz/{camera_id}`** — bidirectional.

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
| `birddog` | BirdDog P200 (NDI) | 480×288 | yolov8s.pt | 40 s @ 30 fps |
| `bolin` | Bolin PTZ (NDI) | 720×488 | yolov8n.pt | 20 s @ 20 fps |

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
│   │   ├── device.py        # select_device(), device_info() — CUDA/MPS/CPU
│   │   ├── ndi_io.py        # NDI source discovery + NDIReceiver (optional SDK)
│   │   ├── ptz_cam.py       # NDIPTZCamera — pan/tilt/zoom/stop/autofocus
│   │   ├── detection.py     # Detector (YOLOv8+DeepSort), BBox, SpeedEstimator
│   │   ├── controllers.py   # PanController, ZoomController (EMA, rate-limiting)
│   │   ├── recorder.py      # VideoRecorder (CFR-paced MP4 output)
│   │   ├── hud.py           # draw_hud() overlay on frame
│   │   ├── session.py       # App-wide singleton; thread→asyncio frame bridge
│   │   └── track_loop.py    # TrackLoop daemon thread; RtspCapture
│   ├── api/
│   │   ├── cameras.py       # /api/cameras/* (multi-camera management, config)
│   │   ├── ptz.py           # ws://.../ws/ptz/{camera_id}  (commands + telemetry)
│   │   ├── webrtc.py        # /api/webrtc/{camera_id}/offer  (SDP exchange, NDIVideoTrack)
│   │   ├── recordings.py    # /api/recordings/* + /api/logs/*
│   │   ├── system.py        # /api/system/info + /api/system/metrics
│   │   └── models.py        # /api/models  (model registry)
│   ├── main.py              # FastAPI app, lifespan, SPA fallback, entry point
│   ├── install.py           # Auto-detecting installer (Jetson/CUDA/macOS/RPi/CPU)
│   └── requirements.txt     # All deps except torch (installed by install.py)
├── frontend/
│   └── src/
│       ├── api/client.ts    # Typed fetch wrappers for all REST endpoints
│       ├── types/index.ts   # Shared TypeScript interfaces
│       ├── hooks/
│       │   ├── useWebSocket.ts  # Auto-reconnecting WS; exposes sendPanTilt etc.
│       │   ├── useWebRTC.ts     # RTCPeerConnection lifecycle; returns stream
│       │   └── useGamepad.ts    # rAF-based Gamepad API polling; deadzone
│       ├── tabs/
│       │   ├── CameraTab.tsx    # Source discovery, connect, config sliders
│       │   ├── ControlTab.tsx   # Live video, joystick status, mode, recording
│       │   └── LogsTab.tsx      # Recordings browser + inline player, CSV logs
│       └── App.tsx              # Tab shell; single WS instance shared to tabs
├── archive/
│   ├── ndi_det.py               # Original YOLO+DeepSort pan+zoom script
│   ├── ndi_det_zoom.py          # Enhanced: multi-class, speed estimation
│   ├── ndi_joystick_log_ms.py   # Manual joystick PTZ with CSV logging
│   └── README.md                # Original project notes
└── README.md                    # This file
```
