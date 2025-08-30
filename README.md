# NDI Object Tracker with YOLOv8 + DeepSORT + PTZ (BirdDog)

Real-time object tracking over NDI with YOLOv8 and DeepSORT, with automatic PTZ (pan/tilt/zoom) control for BirdDog PTZ cameras.
Saves annotated recordings (with bounding boxes + HUD showing FPS and timecode) at a fixed, accurate duration.

## Features

-Flexible object detection — track any YOLO class (people, animals, cars, custom-trained objects, etc.)

-Stable PTZ control via NDI metadata (BirdDog XML)

   -Proportional pan controller with hysteresis & watchdog (no “drifting forever”)

   -Smoothed auto-zoom (EMA + hysteresis): zoom in when the subject is far, zoom out when near

-Fixed-FPS recording with accurate duration (no 20-sec clip turning into 34 sec)

-Live preview + HUD overlay burned into recordings (REC, FPS, elapsed/total time)

-Configurable: dead-zones, thresholds, speeds, inversion flags, recording FPS

## Demo

-Live window shows:

  -Camera video with bounding boxes

  -Dead-zone / threshold rails

  -HUD with recording status, FPS, and timecode

-Camera automatically pans/zooms to keep tracked objects centered and sized

-A 20-second annotated clip is saved under videos/with_box/

## Prerequisites
### Hardware

-Windows PC with NVIDIA GPU (recommended; CPU mode works but slower)

-BirdDog PTZ camera (e.g., X1) on the same network, with NDI enabled

### Software

-NDI Tools (runtime for NDI SDK)

-Python 3.10+ (conda recommended)

-CUDA-enabled PyTorch (if GPU acceleration is desired)

## Installation
### 1) Create conda env
conda create -n ndi_yolo_ptz python=3.10 -y
conda activate ndi_yolo_ptz

### 2) Install CUDA-enabled PyTorch (example for CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

verify-
python - << 'PY'
import torch
print("Torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
PY

### 3) Install dependencies
pip install ultralytics==8.* opencv-python deep-sort-realtime numpy

### 4) Install NDI Python bindings
pip install ndi-python

## Configuration
All parameters are at the top of the script.

## Detection
# Detection classes (COCO IDs or None for all)
# Example: 0=person, 16=dog, 17=cat, 39=bottle
DETECT_CLASSES = None   # None = detect all classes

Examples:
  -Only people → DETECT_CLASSES = [0]

  -Dogs and cats → DETECT_CLASSES = [16, 17]

  -All objects → DETECT_CLASSES = None

If you use a custom YOLO model, its own label set will be used.

## PTZ Controls
| Key                   | Purpose                                        | Typical    |        |    |
| --------------------- | ---------------------------------------------- | ---------- | ------ | -- |
| `DEAD_ZONE_PX`        | No pan if                                      | dx         | ≤ this | 40 |
| `PAN_THRESH_PX`       | Outer hysteresis band                          | 100        |        |    |
| `PAN_KP`              | Proportional gain for pan speed                | 0.9        |        |    |
| `PAN_MAX` / `PAN_MIN` | Max/min pan speeds                             | 0.8 / 0.2  |        |    |
| `INVERT_PAN`          | Flip direction if camera mount/mirror requires | True/False |        |    |
| `ZOOM_IN_FRAC`        | bbox width fraction below → zoom in            | 0.18       |        |    |
| `ZOOM_OUT_FRAC`       | bbox width fraction above → zoom out           | 0.40       |        |    |
| `ZOOM_SPEED`          | Zoom speed (0–1)                               | 0.6        |        |    |
| `INVERT_ZOOM`         | Flip zoom direction                            | False      |        |    |
| `EMA_ALPHA`           | Smooth bbox width fraction                     | 0.45       |        |    |

## Recording
| Key               | Purpose                                 | Typical   |
| ----------------- | --------------------------------------- | --------- |
| `RECORD_DURATION` | Seconds per clip after detection starts | 20        |
| `REC_FPS`         | Fixed FPS for saved video               | 15/20/30  |
| `REC_RES`         | Output resolution (WxH)                 | (480,288) |

## How it Works

### 1. Capture & Detection

  -Frames received via NDIlib.recv_capture_v2

  -YOLOv8 detects chosen classes

  -DeepSORT assigns stable IDs

### 2. Pan Controller

  -Error = target center − frame center

  -Dead-zone & hysteresis prevent jitter

  -Error scaled by gain (KP) → PTZ pan speed

  -Always sends explicit stop when centered or lost

### 3. Zoom Controller

  -Uses bbox width fraction as distance proxy

  -EMA smoothing + two thresholds prevent hunting

  -Sends zoom speed or explicit stop

### 4. Recording

  -Starts when a target is confirmed

  -Fixed-FPS pacing loop writes exactly REC_FPS × RECORD_DURATION frames

  -HUD drawn on both live and recorded frames

## Running
1. Connect BirdDog PTZ camera (enable NDI, ensure discoverable)

2. Adjust SOURCE_MATCH in config to match part of your camera’s NDI name (e.g., "BIRDDOG")

3. Run:
   python ndi_yolo_ptz.py
4. Press Q to quit.
   Clips will appear in:
   videos/with_box/output_YYYYMMDD_HHMMSS_with_box.mp4

## Tips & Tuning
### Low FPS?

  -Ensure CUDA build of PyTorch

  -Reduce VIDEO_RES

  -Close other GPU-hungry apps

### Pan overshoots or jitters?
  -Increase DEAD_ZONE_PX or PAN_THRESH_PX

  -Reduce PAN_KP or PAN_MAX
### Zoom hunts?
  -Increase gap between ZOOM_IN_FRAC and ZOOM_OUT_FRAC

  -Increase EMA_ALPHA to smooth more
### Wrong direction?
  -Toggle INVERT_PAN or INVERT_ZOOM

  -Also check BirdDog camera menu: Mount, Mirror/Flip, PT Direction

## Project Structure
.
├── ndi_yolo_ptz.py        # main script
├── videos/
│   └── with_box/          # recorded annotated clips
└── README.md              # this file

## Troubleshooting

### Camera moves opposite of expected

  -Flip INVERT_PAN or INVERT_ZOOM in config

  -Or change camera settings (Mount, Mirror/Flip, PT Direction)

### Recording too long/short

  -This repo uses a fixed-FPS paced writer — clips are exactly RECORD_DURATION

  -If you change writing logic, ensure CFR pacing

### NDI source not found

  -Ensure NDI Tools installed, firewall allows UDP/TCP 5960–5970

  -Verify PC and BirdDog are on the same subnet

  -Adjust SOURCE_MATCH

## Roadmap
  -CLI arguments for all config

  -Multiple target selection strategies (closest, largest, etc.)

  -RTSP input / HTTP PTZ fallback

  -Overlay zoom level if exposed by BirdDog API

  -Manual record hotkey (r)


## Acknowledgements
- Ultralytics YOLOv8, https://github.com/ultralytics/ultralytics
- DeepSORT Realtime, https://github.com/levan92/deep-sort-realtime
- NDI SDK, https://ndi.tv/sdk/
- BirdDog PTZ, https://birddog.tv
