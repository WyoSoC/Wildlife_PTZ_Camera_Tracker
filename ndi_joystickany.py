#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import numpy as np
import NDIlib as ndi
import time
import sys
import csv
import os
import psutil
import torch
from datetime import datetime, timezone

# =====================================================
# CONFIGURATION
# =====================================================
CAMERA_NAME = "hx"        # partial name of your NDI camera
JOYSTICK_MATCH = "6 axis"   # keyword to select controller (e.g. "8bitdo", "dualsense", "xbox")
PAN_SPEED_SCALE = 0.8
TILT_SPEED_SCALE = 0.8
ZOOM_SPEED_SCALE = 1.0
ZOOM_SMOOTH_ALPHA = 0.35
CMD_INTERVAL = 1.0 / 100.0      # target 60 Hz
LOG_FOLDER = "joystick control logs (s)"

# =====================================================
# NDI HELPERS
# =====================================================
def ndi_init_and_find_source(match: str):
    if not ndi.initialize():
        raise RuntimeError("NDI initialization failed")
    finder = ndi.find_create_v2()
    time.sleep(1)
    sources = ndi.find_get_current_sources(finder) or []
    names = [getattr(s, "ndi_name", getattr(s, "p_ndi_name", "")) for s in sources]
    print("Available NDI sources:", names)
    for s in sources:
        name = getattr(s, "ndi_name", getattr(s, "p_ndi_name", ""))
        if match.lower() in name.lower():
            print("Matched source:", name)
            return finder, s
    raise RuntimeError(f"No source found matching '{match}'")

def ndi_create_receiver_and_connect(source):
    recv = ndi.recv_create_v3()
    if not recv:
        raise RuntimeError("NDI receiver creation failed")
    ndi.recv_connect(recv, source)
    print("Connected to:", getattr(source, "ndi_name", getattr(source, "p_ndi_name", "UNKNOWN")))
    return recv

def ndi_frame_keepalive(recv, timeout_ms=30):
    t, v, _, _ = ndi.recv_capture_v2(recv, timeout_ms)
    if t == ndi.FRAME_TYPE_VIDEO and v:
        ndi.recv_free_video_v2(recv, v)

def ndi_send_xml(recv, xml: str):
    try:
        meta = ndi.MetadataFrame()
        meta.data, meta.timecode = xml, 0
        ndi.recv_send_metadata(recv, meta)
    except Exception:
        pass

def send_ptz_pan_tilt(recv, pan, tilt):
    xml = f'<ntk_ptz_pan_tilt_speed pan_speed="{pan:.3f}" tilt_speed="{tilt:.3f}"/>'
    ndi_send_xml(recv, xml)

def send_ptz_zoom(recv, zoom):
    xml1 = f'<ntk_ptz_zoom_speed zoom_speed="{zoom:.3f}"/>'
    xml2 = f'<ndi_ptz_zoom_speed zoom_speed="{zoom:.3f}"/>'
    ndi_send_xml(recv, xml1)
    ndi_send_xml(recv, xml2)

def trigger_autofocus(recv):
    ndi_send_xml(recv, '<ntk_ptz_focus_auto autofocus="on"/>')

def stop_ptz(recv):
    ndi_send_xml(recv, '<ntk_ptz_pan_tilt_speed pan_speed="0.000" tilt_speed="0.000"/>')
    ndi_send_xml(recv, '<ntk_ptz_zoom_speed zoom_speed="0.000"/>')
    ndi_send_xml(recv, '<ndi_ptz_zoom_speed zoom_speed="0.000"/>')

# =====================================================
# JOYSTICK HELPER
# =====================================================
def find_joystick(match: str):
    pygame.init()
    pygame.joystick.init()

    count = pygame.joystick.get_count()
    if count == 0:
        raise RuntimeError("No joystick detected.")

    print(f"Detected {count} joystick(s):")
    found_index = None
    for i in range(count):
        name = pygame.joystick.Joystick(i).get_name()
        print(f"[{i}] {name}")
        if match.lower() in name.lower():
            found_index = i

    if found_index is None:
        print(f"No joystick matching '{match}' found, using first detected one.")
        found_index = 0

    js = pygame.joystick.Joystick(found_index)
    js.init()
    print("Using controller:", js.get_name())
    return js

# =====================================================
# MAIN LOOP
# =====================================================
def main():
    finder, cam_src = ndi_init_and_find_source(CAMERA_NAME)
    recv = ndi_create_receiver_and_connect(cam_src)

    # === Prepare logging ===
    os.makedirs(LOG_FOLDER, exist_ok=True)
    log_filename = f"{LOG_FOLDER}/ptz_control_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(log_filename, "w", newline="") as log_file:
        writer = csv.writer(log_file)
        writer.writerow([
            "DateTime", "PanSpeed", "TiltSpeed", "ZoomSpeed",
            "PanDirection", "TiltDirection", "ZoomDirection",
            "CPU_Usage(%)", "GPU_Usage(%)"
        ])
        log_file.flush()
        print("Logging PTZ commands to:", log_filename)

        # === Joystick setup ===
        js = find_joystick(JOYSTICK_MATCH)
        print("Controls: Left Stick = Pan/Tilt | Right Stick Up/Down = Zoom | X = Stop | Ctrl+C = Quit")

        last_cmd_time = 0.0
        zoom_smooth = 0.0
        loop_counter = 0
        rate_start = time.time()

        try:
            while True:
                pygame.event.pump()
                now = time.time()

                # === PAN/TILT ===
                x_axis = js.get_axis(0)
                y_axis = -js.get_axis(1)
                if abs(x_axis) < 0.1:
                    x_axis = 0
                if abs(y_axis) < 0.1:
                    y_axis = 0
                pan_speed = -x_axis * PAN_SPEED_SCALE
                tilt_speed = y_axis * TILT_SPEED_SCALE
                pan_dir = "Right" if pan_speed > 0 else "Left" if pan_speed < 0 else "None"
                tilt_dir = "Up" if tilt_speed > 0 else "Down" if tilt_speed < 0 else "None"

                # === ZOOM ===
                zoom_axis = -js.get_axis(4)
                zoom_raw = (zoom_axis ** 3) * ZOOM_SPEED_SCALE if abs(zoom_axis) >= 0.1 else 0.0
                zoom_smooth = (ZOOM_SMOOTH_ALPHA * zoom_raw +
                               (1 - ZOOM_SMOOTH_ALPHA) * zoom_smooth)
                if abs(zoom_smooth) < 0.05:
                    zoom_smooth = 0.0
                zoom_dir = "In" if zoom_smooth > 0 else "Out" if zoom_smooth < 0 else "None"
                if abs(zoom_smooth) > 0.05:
                    trigger_autofocus(recv)

                # === System monitoring ===
                cpu_usage = psutil.cpu_percent(interval=None)
                if torch.cuda.is_available():
                    try:
                        gpu_util = torch.cuda.utilization(0)
                    except Exception:
                        gpu_util = 0.0
                else:
                    gpu_util = 0.0

                # === Command + Logging ===
                if now - last_cmd_time >= CMD_INTERVAL:
                    send_ptz_pan_tilt(recv, pan_speed, tilt_speed)
                    send_ptz_zoom(recv, zoom_smooth)

                    iso_time = datetime.now(timezone.utc).isoformat()
                    writer.writerow([
                        iso_time,
                        f"{pan_speed:.3f}", f"{tilt_speed:.3f}", f"{zoom_smooth:.3f}",
                        pan_dir, tilt_dir, zoom_dir,
                        f"{cpu_usage:.2f}", f"{gpu_util:.2f}"
                    ])
                    log_file.flush()
                    last_cmd_time = now

                ndi_frame_keepalive(recv)

                # Stop button
                if js.get_button(0):
                    stop_ptz(recv)
                    print("PTZ stopped.")

                loop_counter += 1
                if now - rate_start >= 1.0:
                    print(f"Loop rate: {loop_counter} Hz | CPU: {cpu_usage:.1f}% | GPU: {gpu_util:.1f}%")
                    loop_counter = 0
                    rate_start = now

                time.sleep(1.0 / 120.0)

        except KeyboardInterrupt:
            print("Interrupted by user.")
        finally:
            try:
                stop_ptz(recv)
                ndi.recv_destroy(recv)
                ndi.find_destroy(finder)
                ndi.destroy()
            except:
                pass
            pygame.quit()
            print("Clean exit. Log saved to:", log_filename)


if __name__ == "__main__":
    main()
