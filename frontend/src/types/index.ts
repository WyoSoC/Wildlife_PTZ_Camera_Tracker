// ── Server connection ──────────────────────────────────────────────────────────

export interface ServerConfig {
  url:    string
  name:   string
  apiKey: string
}

// ── Camera ────────────────────────────────────────────────────────────────────

export interface CameraListItem {
  camera_id:   string
  source_name: string
  connected:   boolean
  running:     boolean
  mode:        'manual' | 'auto_track'
  device:      string
  device_name: string
}

export interface NDISource {
  name: string
  type: 'ndi' | 'reolink'
}

export interface CameraStatus {
  camera_id:    string
  connected:    boolean
  running:      boolean
  source_name:  string
  source_match: string
  rtsp_url:     string
  mode:         'manual' | 'auto_track'
  device:       string
  device_name:  string
}

// ── Config ────────────────────────────────────────────────────────────────────

export interface PanConfig {
  stable_zone_h_px:   number
  stable_zone_v_px: number
  kp:             number
  max_speed:      number
  min_speed:      number
  invert:         boolean
}

export interface ZoomConfig {
  zoom_in_frac:  number
  zoom_out_frac: number
  speed:         number
  invert:        boolean
  ema_alpha:     number
}

export interface HomeConfig {
  pan:    number
  tilt:   number
  zoom:   number
  is_set: boolean
}

export interface AreaConfig {
  enabled:   boolean
  pan_min:   number
  pan_max:   number
  tilt_min:  number
  tilt_max:  number
  scan_zoom: number
}

export interface ScanConfig {
  enabled:    boolean
  rows:       number
  cols:       number
  travel_sec: number
  dwell_sec:  number
}

export interface CameraConfig {
  camera:  { source_match: string; reolink_rtsp_url: string }
  pan:     PanConfig
  zoom:    ZoomConfig
  track:   { detect_classes: number | null; model_path: string; lock_confidence: number; tracker_max_age: number }
  command: { no_track_stop_sec: number; lock_off_sec: number }
  record:  { duration_sec: number; fps: number; record_res: [number, number] }
  speed:   { hfov_deg: number }
  home:    HomeConfig
  area:    AreaConfig
  scan:    ScanConfig
}

export interface ConfigUpdate {
  pan_stable_zone_h_px?:    number
  pan_stable_zone_v_px?:  number
  pan_kp?:              number
  pan_max_speed?:       number
  pan_min_speed?:       number
  pan_invert?:          boolean
  zoom_in_frac?:        number
  zoom_out_frac?:       number
  zoom_speed?:          number
  zoom_invert?:         boolean
  zoom_ema_alpha?:      number
  detect_classes?:      number | null
  lock_confidence?:     number
  tracker_max_age?:     number
  no_track_stop_sec?:   number
  lock_off_sec?:        number
  record_duration_sec?: number
  record_fps?:          number
  record_res?:          [number, number]
  hfov_deg?:            number
  model_path?:          string
  home_pan?:            number
  home_tilt?:           number
  home_zoom?:           number
  home_is_set?:         boolean
  area_enabled?:        boolean
  area_pan_min?:        number
  area_pan_max?:        number
  area_tilt_min?:       number
  area_tilt_max?:       number
  area_scan_zoom?:      number
  scan_enabled?:        boolean
  scan_rows?:           number
  scan_cols?:           number
  scan_travel_sec?:     number
  scan_dwell_sec?:      number
}

// ── Models ────────────────────────────────────────────────────────────────────

export interface ModelInfo {
  name:            string
  path:            string
  description:     string
  species:         string[]
  source:          string
  auto_download:   boolean
  detect_classes:  number[] | null
  downloaded:      boolean
  repo_id:         string | null
  download_url:    string | null
  source_url:      string | null
}

// ── Telemetry ─────────────────────────────────────────────────────────────────

export interface Telemetry {
  type:        'telemetry'
  connected:   boolean
  source_name: string
  mode:        'manual' | 'auto_track'
  fps:         number
  detected:    boolean
  track_id:    number | null
  confidence:  number
  speed_px:    number
  speed_deg:   number
  wfrac_ema:   number
  scan_phase:  'idle' | 'scanning' | 'locked'
  rec_active:  boolean
  rec_elapsed: number
  rec_total:   number
}

// ── System metrics ────────────────────────────────────────────────────────────

export interface SystemMetrics {
  cpu_percent: number | null
  memory: {
    percent:  number
    used_gb:  number
    total_gb: number
  }
  gpu: {
    name:              string
    utilization_pct:   number
    memory_used_gb:    number
    memory_total_gb:   number
    temperature_c:     number
    power_watts:       number | null
  } | null
}

export interface SystemInfo {
  os:          string
  machine:     string
  python:      string
  device:      string
  device_name: string
  psutil:      boolean
  nvml:        boolean
}

// ── Recordings / Logs ─────────────────────────────────────────────────────────

export interface Recording {
  filename: string
  size_mb:  number
  modified: string
}

export interface LogFile {
  filename: string
  rows:     number
  modified: string
}

// ── NTP time sync ─────────────────────────────────────────────────────────────

export interface NtpStatus {
  offset_sec: number
  last_sync:  string | null
  server:     string
  synced:     boolean
}

// ── User-saved tracking profiles ─────────────────────────────────────────────

export interface UserProfile {
  name:        string
  saved_at:    string | null
  description: string
}

// ── WebSocket hook ────────────────────────────────────────────────────────────

export interface WebSocketHook {
  telemetry:     Telemetry | null
  wsConnected:   boolean
  sendPanTilt:   (pan: number, tilt: number) => void
  sendZoom:      (speed: number) => void
  sendStop:      () => void
  sendAutofocus: () => void
  setMode:       (mode: 'manual' | 'auto_track') => void
  setRecording:  (action: 'start' | 'stop') => void
}
