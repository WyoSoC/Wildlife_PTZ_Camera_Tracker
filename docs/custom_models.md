# Custom Model Guide — Wildlife PTZ Camera Tracker

This guide explains how to train, export, and load your own YOLO detection model into the tracker.

---

## Overview

The tracker uses [Ultralytics YOLO](https://docs.ultralytics.com/) (v8 / v10 / v11) `.pt` files.
Any model you train or find on HuggingFace can be added from the **Cameras & Config** tab
under **Add Custom HuggingFace Model**.

Custom `.pt` files are stored in `models/custom/` and appear automatically in the model list on refresh.

---

## 1 — Training Your Own Model

### 1.1 Dataset format

YOLO expects a dataset in the following layout:

```
dataset/
  images/
    train/   *.jpg / *.png
    val/
  labels/
    train/   *.txt  (one file per image)
    val/
  data.yaml
```

Each `.txt` label file contains one detection per line:

```
<class_id>  <cx>  <cy>  <width>  <height>
```

All values are **normalised 0–1** relative to image size. `class_id` is a zero-based integer.

`data.yaml` example:
```yaml
path:  /path/to/dataset
train: images/train
val:   images/val

nc: 1                  # number of classes
names: ['bald_eagle']  # class names
```

### 1.2 Training

```bash
pip install ultralytics
yolo train model=yolov8s.pt data=data.yaml epochs=100 imgsz=640 batch=16
```

The best checkpoint is saved to `runs/detect/train/weights/best.pt`.

For GPU acceleration on the RTX 4090:
```bash
yolo train model=yolov8s.pt data=data.yaml epochs=100 imgsz=640 batch=32 device=0
```

### 1.3 Validate and export

```bash
# Check mAP on the validation split
yolo val model=runs/detect/train/weights/best.pt data=data.yaml

# Optional: export to ONNX for faster CPU inference
yolo export model=best.pt format=onnx
```

---

## 2 — Uploading to HuggingFace

### 2.1 Create a repository

1. Log in at [huggingface.co](https://huggingface.co) and click **New Model**.
2. Set visibility to **Public** (required for unauthenticated download).
3. Name it something descriptive, e.g. `your-name/bald-eagle-yolo8s`.

### 2.2 Upload your weights

```bash
pip install huggingface_hub
huggingface-cli login

# Upload the best checkpoint
huggingface-cli upload your-name/bald-eagle-yolo8s \
  runs/detect/train/weights/best.pt \
  best.pt
```

Or via the HuggingFace web UI: open your repo → **Files** → **Upload files**.

### 2.3 Write a model card (optional but recommended)

Add a `README.md` to your repo describing:
- What species / classes the model detects
- Training dataset size and source
- Validation mAP scores
- Recommended input resolution

---

## 3 — Loading the Model in the Tracker

In the **Cameras & Config** tab, scroll to **Add Custom HuggingFace Model**:

| Field | Example | Notes |
|---|---|---|
| HuggingFace URL or owner/repo | `your-name/bald-eagle-yolo8s` | Full URL or short form |
| Filename in repo | `best.pt` | Default — the checkpoint filename you uploaded |
| Local name (optional) | `bald_eagle` | How it appears in the model list |

Click **Download**. The file is saved to `models/custom/<local_name>.pt` and will appear
in the **Custom Models** section immediately.

---

## 4 — Notes

- The tracker runs YOLO inference at the configured processing resolution (default 640×360). Higher resolution improves accuracy but reduces FPS.
- If your model detects a single class, set **Detect classes** to `0` in the Controls tab to restrict tracking to that class.
- Models trained on aerial or distant views tend to generalise better across PTZ zoom levels.
- Consider data augmentation (random crops, mosaic, perspective) to improve robustness to partial occlusion and motion blur.

---

## 5 — Finding Pre-trained Wildlife Models

Search HuggingFace for community models:

- [HuggingFace model hub — wildlife](https://huggingface.co/models?search=wildlife+yolo)
- [University of Wyoming Wildlife Models](https://huggingface.co/UWyo) — used as built-in specialized models
- [African Wildlife YOLO](https://huggingface.co/models?search=african+wildlife+yolo)

Paste the model URL directly into the **Add Custom HuggingFace Model** form.
