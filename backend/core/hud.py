from __future__ import annotations
import cv2
import numpy as np


def draw_hud(
    img: np.ndarray,
    *,
    rec_on:    bool,
    fps:       float,
    elapsed:   float = 0.0,
    total:     float = 0.0,
    speed_px:  float = 0.0,
    speed_deg: float = 0.0,
    detected:  bool  = False,
    timestamp: str   = '',
) -> None:
    """
    Draw a compact telemetry bar on img in-place (top strip).

    Layout (left → right):
      ● [red dot if recording]  FPS:XX.X  [SPDpx/s  DEG°/s — only when detected]
                                         [timecode]  [timestamp — right-aligned]
    """
    h, _w = img.shape[:2]
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1
    strip_h = 18
    baseline = 12   # text baseline y-coord within the strip

    # Black background strip
    cv2.rectangle(img, (0, 0), (_w, strip_h), (0, 0, 0), -1)

    # ── Left side ─────────────────────────────────────────────────────────────
    x = 6

    # Recording dot
    if rec_on:
        cv2.circle(img, (x + 4, strip_h // 2), 4, (0, 0, 220), -1)
    x += 14

    # FPS
    fps_txt = f"FPS:{fps:.1f}"
    cv2.putText(img, fps_txt, (x, baseline), font, scale, (190, 190, 190), thick, cv2.LINE_AA)
    x += cv2.getTextSize(fps_txt, font, scale, thick)[0][0] + 10

    # Speed — only shown when a target is detected and locked
    if detected:
        spd_txt = f"{speed_px:.0f}px/s  {speed_deg:.1f}°/s"
        cv2.putText(img, spd_txt, (x, baseline), font, scale, (80, 210, 100), thick, cv2.LINE_AA)

    # ── Right side ────────────────────────────────────────────────────────────
    right_x = _w - 6

    # Timestamp (rightmost)
    if timestamp:
        ts_w = cv2.getTextSize(timestamp, font, scale, thick)[0][0]
        right_x -= ts_w
        cv2.putText(img, timestamp, (right_x, baseline), font, scale, (160, 160, 160), thick, cv2.LINE_AA)
        right_x -= 10

    # Recording timecode (elapsed / total, or elapsed-only for unlimited)
    if rec_on:
        sec = max(0, int(round(elapsed)))
        mm, ss = sec // 60, sec % 60
        if total > 0:
            tot = int(total)
            tc = f"{mm:02d}:{ss:02d}/{tot // 60:02d}:{tot % 60:02d}"
        else:
            tc = f"{mm:02d}:{ss:02d}"
        tc_w = cv2.getTextSize(tc, font, scale, thick)[0][0]
        right_x -= tc_w
        cv2.putText(img, tc, (right_x, baseline), font, scale, (180, 80, 80), thick, cv2.LINE_AA)
