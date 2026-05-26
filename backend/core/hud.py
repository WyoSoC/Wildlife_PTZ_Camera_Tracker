from __future__ import annotations
import cv2
import numpy as np


def draw_hud(
    img: np.ndarray,
    *,
    rec_on: bool,
    fps: float,
    elapsed: float = 0.0,
    total: float = 0.0,
    speed_px: float = 0.0,
    speed_deg: float = 0.0,
) -> None:
    """
    Draw telemetry bar on img in-place (top 22px black strip).
    All parameters are keyword-only to prevent positional mistakes.
    """
    _w = img.shape[1]
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1

    cv2.rectangle(img, (0, 0), (_w, 22), (0, 0, 0), -1)

    if rec_on:
        cv2.circle(img, (10, 11), 5, (0, 0, 255), -1)

    x = 22
    cv2.putText(img, f"REC:{'ON' if rec_on else 'OFF'}", (x, 15), font, scale, (255, 255, 255), thick)
    x += 80
    cv2.putText(img, f"FPS:{fps:.1f}", (x, 15), font, scale, (255, 255, 255), thick)
    x += 75
    cv2.putText(
        img, f"SPD:{speed_px:.0f}px/s|{speed_deg:.1f}°/s",
        (x, 15), font, scale, (255, 255, 255), thick,
    )

    if total > 0:
        sec = max(0, int(round(elapsed)))
        tc = f"{sec // 60:02d}:{sec % 60:02d}/{int(total) // 60:02d}:{int(total) % 60:02d}"
        cv2.putText(img, tc, (_w - 115, 15), font, scale, (255, 255, 255), thick)
