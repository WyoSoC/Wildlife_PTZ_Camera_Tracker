#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, time, collections
from datetime import datetime
import cv2, numpy as np, torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import NDIlib as ndi

# =========== CONFIG ===========
SOURCE_MATCH = "birddog"       # NDI source name (partial, case-insensitive)
VIDEO_RES = (480, 288)         # processing/display resolution
REC_RES   = (480, 288)         # recording resolution
RECORD_DURATION = 40           # seconds after first detection
REC_FPS = 30                   # fixed CFR for saved file (choose 15/20/30)
FRAME_PERIOD = 1.0 / REC_FPS

# PAN controller (proportional, continuous velocity)
DEAD_ZONE_PX = 40              # no movement if |dx| <= this
PAN_THRESH_PX = 100            # start moving only beyond this (outer band)
PAN_KP = 0.9                   # proportional gain -> speed = clamp(KP * dx_norm)
PAN_MAX = 0.8                  # abs max speed (0..1)
PAN_MIN = 0.20                 # minimum speed when moving (to overcome stiction)
INVERT_PAN = True              # set True if visual right needs negative motor pan

# ZOOM controller (EMA + hysteresis, continuous speed)
ZOOM_IN_FRAC  = 0.18           # bbox_w/frame_w below -> zoom in
ZOOM_OUT_FRAC = 0.40           # bbox_w/frame_w above -> zoom out
ZOOM_SPEED = 0.6               # abs zoom speed (0..1)
INVERT_ZOOM = False            # flip if your zoom feels opposite
EMA_ALPHA = 0.45               # smoothing for bbox width fraction

# Command rate limiting / watchdog
CMD_EPS = 0.05                 # only send if speed change > this
CMD_MIN_INTERVAL = 0.05        # min seconds between command changes
NO_TRACK_STOP_SEC = 0.3        # send stop if no confirmed track for this time

NDI_TIMEOUT_MS = 50
SHOW_WINDOW = True
# ==============================

# ---- Folders / recording ----
os.makedirs("videos/with_box", exist_ok=True)

# ---- YOLO + DeepSort ----
model = YOLO("yolov8s.pt")
if torch.cuda.is_available():
    model.to("cuda"); print("🚀 Using CUDA")
else:
    print("⚠️ Using CPU")
tracker = DeepSort(max_age=30)
fps_window = collections.deque(maxlen=30)

# ---- Small HUD helper ----
def _fmt_tc(sec):
    sec = max(0, int(round(sec)))
    return f"{sec//60:02d}:{sec%60:02d}"

def draw_hud(img, rec_on, fps, elapsed=0.0, total=0.0):
    """Draw FPS + REC + timecode on the frame (in-place)."""
    h, w = img.shape[:2]
    pad = 6
    # Background bar
    cv2.rectangle(img, (0,0), (w, 26), (0,0,0), thickness=-1)
    # REC dot
    if rec_on:
        cv2.circle(img, (12, 13), 6, (0,0,255), thickness=-1)
    # Text
    left = 26
    txt1 = f"REC:{'ON' if rec_on else 'OFF'}"
    cv2.putText(img, txt1, (left, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)
    left += 100
    cv2.putText(img, f"FPS:{fps:.1f}", (left, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)
    if total > 0:
        tc = f"{_fmt_tc(elapsed)} / {_fmt_tc(total)}"
        cv2.putText(img, tc, (w-150, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)

# ---- NDI helpers ----
def ndi_init_and_find_source(match: str):
    if not ndi.initialize():
        raise RuntimeError("NDI init failed")
    finder = ndi.find_create_v2()
    time.sleep(1)
    sources = ndi.find_get_current_sources(finder) or []
    for s in sources:
        if match.lower() in s.ndi_name.lower():
            return finder, s
    raise RuntimeError(f"NDI source containing '{match}' not found")

def ndi_create_receiver_and_connect(source):
    recv = ndi.recv_create_v3()
    if not recv:
        raise RuntimeError("NDI recv create failed")
    ndi.recv_connect(recv, source)
    return recv

def ndi_frame_to_bgr(v_frame):
    h, w = v_frame.yres, v_frame.xres
    fb = bytes(v_frame.data)
    if len(fb) == w*h*4:
        return cv2.cvtColor(np.frombuffer(fb, np.uint8).reshape((h, w, 4)), cv2.COLOR_BGRA2BGR)
    if len(fb) == w*h*2:
        return cv2.cvtColor(np.frombuffer(fb, np.uint8).reshape((h, w, 2)), cv2.COLOR_YUV2BGR_UYVY)
    raise ValueError("Unsupported NDI frame format/stride")

def ndi_send_xml(recv, xml: str):
    # Advanced SDK style
    try:
        meta = ndi.MetadataFrame()
        meta.data, meta.timecode = xml, 0
        ndi.recv_send_metadata(recv, meta)
    except Exception:
        # Legacy fallback
        try:
            m = ndi.NDIlib_metadata_frame_t()
            payload = xml.encode("utf-8")
            m.p_data, m.length, m.timecode = payload, len(payload), 0
            ndi.recv_send_metadata(recv, m)
        except Exception as e:
            raise RuntimeError(f"PTZ metadata send failed: {e}")

def send_pan_speed(recv, speed):
    sp = max(-PAN_MAX, min(PAN_MAX, float(speed)))
    if INVERT_PAN: sp = -sp
    if abs(sp) > 0 and abs(sp) < PAN_MIN:
        sp = PAN_MIN if sp > 0 else -PAN_MIN
    xml = f'<ntk_ptz_pan_tilt_speed pan_speed="{sp:.3f}" tilt_speed="0.000"/>'
    ndi_send_xml(recv, xml)

def send_zoom_speed(recv, z):
    zz = max(-1.0, min(1.0, float(z)))
    if INVERT_ZOOM: zz = -zz
    xml = f'<ntk_ptz_zoom_speed zoom_speed="{zz:.3f}"/>'
    ndi_send_xml(recv, xml)

def stop_pan_tilt(recv):
    ndi_send_xml(recv, '<ntk_ptz_pan_tilt_speed pan_speed="0.000" tilt_speed="0.000"/>')

def stop_zoom(recv):
    ndi_send_xml(recv, '<ntk_ptz_zoom_speed zoom_speed="0.000"/>')

# ---- Main ----
def main():
    finder, source = ndi_init_and_find_source(SOURCE_MATCH)
    recv = ndi_create_receiver_and_connect(source)
    print("Connected to:", source.ndi_name)

    if SHOW_WINDOW:
        cv2.namedWindow("NDI Tracking + PTZ", cv2.WINDOW_NORMAL)

    # Recording state
    writer = None
    is_recording = False
    record_start = 0.0
    next_write_t = 0.0
    frames_written = 0
    target_frames = int(REC_FPS * RECORD_DURATION)

    # Controller state
    last_pan_cmd = 0.0
    last_zoom_cmd = 0.0
    last_cmd_time = 0.0
    last_confirmed_time = 0.0
    wfrac_ema = None

    try:
        while True:
            t, v, a, m = ndi.recv_capture_v2(recv, NDI_TIMEOUT_MS)
            now = time.time()

            # Watchdog if no frames
            if t != ndi.FRAME_TYPE_VIDEO:
                if now - last_confirmed_time > NO_TRACK_STOP_SEC:
                    if last_pan_cmd != 0.0: stop_pan_tilt(recv); last_pan_cmd = 0.0
                    if last_zoom_cmd != 0.0: stop_zoom(recv);     last_zoom_cmd = 0.0
                continue

            bgr = ndi_frame_to_bgr(v); ndi.recv_free_video_v2(recv, v)
            frame = cv2.resize(bgr, VIDEO_RES)
            frame_h, frame_w = frame.shape[:2]
            frame_cx = frame_w // 2

            # FPS estimate (windowed)
            fps_window.append(now)
            _fps = len(fps_window) / (fps_window[-1] - fps_window[0]) if len(fps_window) >= 2 else 30

            # ---- Detection every frame ----
            results = model(frame, classes=[0], verbose=False)[0]
            detections = []
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                detections.append(([x1, y1, x2 - x1, y2 - y1], conf, "person"))

            tracks = tracker.update_tracks(detections, frame=frame)
            confirmed = [t for t in tracks if t.is_confirmed()]

            desired_pan = 0.0
            desired_zoom = 0.0
            detected = False

            if confirmed:
                detected = True
                last_confirmed_time = now

                tr = confirmed[0]
                x1, y1, x2, y2 = map(int, tr.to_ltrb())
                cx = (x1 + x2) // 2
                bw = max(1, x2 - x1)
                wfrac = bw / float(frame_w)

                # draw detection box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
                cv2.putText(frame, f"ID:{tr.track_id} w%:{wfrac:.2f}", (x1, max(0, y1-8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,0), 2)

                # ---------- PAN (proportional + hysteresis) ----------
                dx = cx - frame_cx
                if abs(dx) <= DEAD_ZONE_PX:
                    desired_pan = 0.0
                elif abs(dx) <= PAN_THRESH_PX:
                    desired_pan = 0.0
                else:
                    dx_norm = dx / (frame_w * 0.5)  # [-1..1]
                    desired_pan = max(-PAN_MAX, min(PAN_MAX, PAN_KP * dx_norm))

                # ---------- ZOOM (EMA + hysteresis) ----------
                wfrac_ema = (wfrac if wfrac_ema is None
                             else EMA_ALPHA * wfrac + (1 - EMA_ALPHA) * wfrac_ema)
                if wfrac_ema < ZOOM_IN_FRAC:
                    desired_zoom = +ZOOM_SPEED
                elif wfrac_ema > ZOOM_OUT_FRAC:
                    desired_zoom = -ZOOM_SPEED
                else:
                    desired_zoom = 0.0

            # ---------- Command rate-limit + watchdog ----------
            if now - last_cmd_time >= CMD_MIN_INTERVAL:
                # PAN
                if abs(desired_pan - last_pan_cmd) > CMD_EPS:
                    if desired_pan == 0.0:
                        stop_pan_tilt(recv)
                    else:
                        send_pan_speed(recv, desired_pan)
                    last_pan_cmd = desired_pan

                # ZOOM
                if abs(desired_zoom - last_zoom_cmd) > CMD_EPS:
                    if desired_zoom == 0.0:
                        stop_zoom(recv)
                    else:
                        send_zoom_speed(recv, desired_zoom)
                    last_zoom_cmd = desired_zoom

                last_cmd_time = now

            if not confirmed and (now - last_confirmed_time > NO_TRACK_STOP_SEC):
                if last_pan_cmd != 0.0:
                    stop_pan_tilt(recv); last_pan_cmd = 0.0
                if last_zoom_cmd != 0.0:
                    stop_zoom(recv);     last_zoom_cmd = 0.0

            # ---- Recording (with boxes only), FIXED-FPS PACED WRITES ----
            if detected and not is_recording:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(
                    f"videos/with_box/output_{ts}_with_box.mp4",
                    fourcc, REC_FPS, REC_RES
                )
                is_recording = True
                record_start = now
                next_write_t = now
                frames_written = 0
                print(f"🎥 Recording {RECORD_DURATION}s @ {REC_FPS} FPS")

            if is_recording:
                # Write frames at fixed cadence; duplicate latest if loop is slower
                elapsed = now - record_start
                while is_recording and now >= next_write_t and frames_written < int(REC_FPS * RECORD_DURATION):
                    rec_frame = cv2.resize(frame, REC_RES)
                    # draw HUD directly on the recorded frame (includes FPS + timecode)
                    draw_hud(rec_frame, True, _fps, elapsed=frames_written/REC_FPS, total=RECORD_DURATION)
                    writer.write(rec_frame)
                    frames_written += 1
                    next_write_t += FRAME_PERIOD

                if frames_written >= int(REC_FPS * RECORD_DURATION):
                    writer.release(); writer = None; is_recording = False
                    print("✅ Recording complete.")

            # ---- Display ----
            if SHOW_WINDOW:
                # visualize dead-zone / threshold bands + HUD
                dzl, dzr = frame_cx - DEAD_ZONE_PX, frame_cx + DEAD_ZONE_PX
                thl, thr = frame_cx - PAN_THRESH_PX, frame_cx + PAN_THRESH_PX
                cv2.line(frame, (dzl,0), (dzl,frame_h), (50,200,255), 1)
                cv2.line(frame, (dzr,0), (dzr,frame_h), (50,200,255), 1)
                cv2.line(frame, (thl,0), (thl,frame_h), (0,215,255), 1)
                cv2.line(frame, (thr,0), (thr,frame_h), (0,215,255), 1)
                draw_hud(frame, is_recording, _fps,
                         elapsed=(frames_written/REC_FPS if is_recording else 0.0),
                         total=(RECORD_DURATION if is_recording else 0.0))
                cv2.imshow("NDI Tracking + PTZ", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # free metadata if any (some bindings deliver it intermittently)
            if t == ndi.FRAME_TYPE_METADATA and m is not None:
                try: ndi.recv_free_metadata(recv, m)
                except: pass

        # end while
    finally:
        try: stop_pan_tilt(recv); stop_zoom(recv)
        except: pass
        if 'writer' in locals() and writer is not None:
            writer.release()
        if SHOW_WINDOW:
            try: cv2.destroyAllWindows()
            except: pass
        try: ndi.recv_destroy(recv)
        except: pass
        try: ndi.find_destroy(finder)
        except: pass
        try: ndi.destroy()
        except: pass

if __name__ == "__main__":
    main()
