// ── Server connection ──────────────────────────────────────────────────────────

export interface ServerConfig {
  url:    string   // "https://machine.tailXXXX.ts.net" or "http://192.168.x.x:9090"
  name:   string   // user-defined display label
  apiKey: string   // optional API key
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
  dead_zone_px: number
  thresh_px:    number
  kp:           number
  max_speed:    number
  min_speed:    number
  invert:       boolean
}

export interface ZoomConfig {
  zoom_in_frac:  number
  zoom_out_frac: number
  speed:         number
  invert:        boolean
  ema_alpha:     number
}

export interface CameraConfig {
  camera: { source_match: string; reolink_rtsp_url: string }
  pan:    PanConfig
  zoom:   ZoomConfig
  track:  { detect_classes: number | null; model_path: string }
  record: { duration_sec: number; fps: number; record_res: [number, number] }
  speed:  { hfov_deg: number }
}

export interface ConfigUpdate {
  pan_dead_zone_px?:    number
  pan_thresh_px?:       number
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
  record_duration_sec?: number
  record_fps?:          number
  hfov_deg?:            number
  model_path?:          string
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
