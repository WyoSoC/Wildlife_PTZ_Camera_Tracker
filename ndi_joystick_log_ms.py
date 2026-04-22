#!/usr/bin/env python
# coding: utf-8

# In[3]:


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame, cv2, numpy as np, NDIlib as ndi, time, sys, csv, os
from datetime import datetime

# =====================================================
# CONFIGURATION
# =====================================================
CAMERA_NAME = "bolin"
PAN_SPEED_SCALE = 0.8
TILT_SPEED_SCALE = 0.8
ZOOM_SPEED_SCALE = 3.0
ZOOM_SMOOTH_ALPHA = 0.35
CMD_INTERVAL = 0.05
SHOW_VIDEO = True
LOG_FOLDER = "joystick control logs (ms)"

# =====================================================
# NDI HELPERS
# =====================================================
def ndi_init_and_find_source(match: str):
    if not ndi.initialize():
        raise RuntimeError("NDI init failed")
    finder = ndi.find_create_v2()
    time.sleep(1)
    sources = ndi.find_get_current_sources(finder) or []
    names = [getattr(s, "ndi_name", getattr(s, "p_ndi_name", "")) for s in sources]
    print("📡 Sources:", names)
    for s in sources:
        name = getattr(s, "ndi_name", getattr(s, "p_ndi_name", ""))
        if match.lower() in name.lower():
            print(f"Matched: {name}")
            return finder, s
    raise RuntimeError(f"Source '{match}' not found")

def ndi_create_receiver_and_connect(source):
    recv = ndi.recv_create_v3()
    if not recv:
        raise RuntimeError("NDI recv create failed")
    ndi.recv_connect(recv, source)
    print(f"Connected to: {getattr(source, 'ndi_name', getattr(source, 'p_ndi_name', 'UNKNOWN'))}")
    return recv

def ndi_frame_to_bgr(v_frame):
    h, w = v_frame.yres, v_frame.xres
    fb = bytes(v_frame.data)
    if len(fb) == w * h * 4:
        return cv2.cvtColor(np.frombuffer(fb, np.uint8).reshape((h, w, 4)), cv2.COLOR_BGRA2BGR)
    if len(fb) == w * h * 2:
        return cv2.cvtColor(np.frombuffer(fb, np.uint8).reshape((h, w, 2)), cv2.COLOR_YUV2BGR_UYVY)
    return None

def ndi_send_xml(recv, xml: str):
    try:
        meta = ndi.MetadataFrame()
        meta.data, meta.timecode = xml, 0
        ndi.recv_send_metadata(recv, meta)
    except Exception as e:
        print(f"PTZ send failed: {e}")

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
# MAIN
# =====================================================
def main():
    finder, cam_src = ndi_init_and_find_source(CAMERA_NAME)
    recv = ndi_create_receiver_and_connect(cam_src)

    # === Prepare logging ===
    os.makedirs(LOG_FOLDER, exist_ok=True)
    log_filename = f"{LOG_FOLDER}/ptz_control_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_file = open(log_filename, "w", newline="")
    log_writer = csv.writer(log_file)
    log_writer.writerow(["Timestamp", "PanSpeed", "TiltSpeed", "ZoomSpeed"])
    print(f"📝 Logging PTZ commands to: {log_filename}")

    # === Joystick setup ===
    pygame.init(); pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("❌ No joystick detected."); sys.exit(1)
    js = pygame.joystick.Joystick(0); js.init()
    print(f"Controller: {js.get_name()}")
    print("Controls → Left Stick: Pan/Tilt | Right Stick Up/Down: Zoom In/Out | X=Stop | Q/Ctrl+C=Quit\n")

    if SHOW_VIDEO: cv2.namedWindow("NDI Preview", cv2.WINDOW_NORMAL)
    last_cmd_time = 0.0
    zoom_smooth = 0.0

    try:
        while True:
            pygame.event.pump()
            now = time.time()

            # ====== PAN/TILT ======
            x_axis = js.get_axis(0)
            y_axis = -js.get_axis(1)
            if abs(x_axis) < 0.1: x_axis = 0
            if abs(y_axis) < 0.1: y_axis = 0
            pan_speed = -x_axis * PAN_SPEED_SCALE
            tilt_speed = y_axis * TILT_SPEED_SCALE

            # ====== RIGHT STICK ZOOM ======
            zoom_axis = -js.get_axis(3)
            if abs(zoom_axis) < 0.1:
                zoom_raw = 0.0
            else:
                zoom_raw = (zoom_axis ** 3) * ZOOM_SPEED_SCALE

            zoom_smooth = (ZOOM_SMOOTH_ALPHA * zoom_raw +
                           (1 - ZOOM_SMOOTH_ALPHA) * zoom_smooth)
            if abs(zoom_smooth) < 0.05:
                zoom_smooth = 0.0

            if abs(zoom_smooth) > 0.05:
                trigger_autofocus(recv)

            # === Send PTZ commands ===
            if now - last_cmd_time >= CMD_INTERVAL:
                send_ptz_pan_tilt(recv, pan_speed, tilt_speed)
                send_ptz_zoom(recv, zoom_smooth)
                # === Log to CSV ===
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                log_writer.writerow([ts, f"{pan_speed:.3f}", f"{tilt_speed:.3f}", f"{zoom_smooth:.3f}"])
                log_file.flush()
                last_cmd_time = now

            # === Stop ===
            if js.get_button(0):
                stop_ptz(recv)
                print("Stop")

            # === Display live preview ===
            if SHOW_VIDEO:
                t, v, _, _ = ndi.recv_capture_v2(recv, 30)
                if t == ndi.FRAME_TYPE_VIDEO and v:
                    frame = ndi_frame_to_bgr(v)
                    if frame is not None:
                        cv2.imshow("NDI Preview", frame)
                    ndi.recv_free_video_v2(recv, v)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    finally:
        try:
            stop_ptz(recv)
            ndi.recv_destroy(recv); ndi.find_destroy(finder); ndi.destroy()
        except: pass
        log_file.close()
        pygame.quit()
        if SHOW_VIDEO: cv2.destroyAllWindows()
        print("Clean exit and log saved")

# =====================================================
if __name__ == "__main__":
    main()


# In[ ]:




