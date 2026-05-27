import type {
  CameraConfig, CameraListItem, CameraStatus, ConfigUpdate,
  ModelInfo, NDISource, Recording, LogFile, SystemMetrics, SystemInfo,
} from '../types'

// ── Server configuration ───────────────────────────────────────────────────────
// Call setServerConfig() from the ConnectScreen before any API call.
// Defaults allow the Vite dev-server proxy to work transparently.

let _serverUrl = ''   // e.g. "https://machine.tailXXXX.ts.net"
let _apiKey    = ''

export function setServerConfig(url: string, apiKey: string): void {
  _serverUrl = url.replace(/\/$/, '')
  _apiKey    = apiKey
}

export function getServerUrl(): string {
  return _serverUrl
}

/** Convert an http(s) server URL to the ws(s) equivalent. */
export function wsUrl(path: string): string {
  const base = _serverUrl || `${window.location.protocol}//${window.location.host}`
  return base.replace(/^http/, 'ws') + path
}

// ── Fetch helpers ──────────────────────────────────────────────────────────────

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...extra }
  if (_apiKey) h['X-API-Key'] = _apiKey
  return h
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(_serverUrl + path, { headers: headers() })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(_serverUrl + path, {
    method:  'POST',
    headers: headers(body != null ? { 'Content-Type': 'application/json' } : {}),
    body:    body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(_serverUrl + path, {
    method:  'PUT',
    headers: headers({ 'Content-Type': 'application/json' }),
    body:    JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(_serverUrl + path, { method: 'DELETE', headers: headers() })
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// ── API surface ────────────────────────────────────────────────────────────────

export const api = {
  cameras: {
    list: () =>
      get<{ cameras: CameraListItem[] }>('/api/cameras'),

    create: (camera_id?: string, profile?: string) =>
      post<{ status: string; camera_id: string }>('/api/cameras', { camera_id, profile }),

    remove: (cameraId: string) =>
      del<{ status: string }>(`/api/cameras/${cameraId}`),

    discover: () =>
      get<{ sources: NDISource[] }>('/api/cameras/discover'),

    connect: (cameraId: string, source_match: string, source_type = 'ndi', rtsp_url?: string) =>
      post<{ status: string }>(`/api/cameras/${cameraId}/connect`, {
        source_match, source_type, rtsp_url,
      }),

    start: (cameraId: string) =>
      post<{ status: string; running: boolean }>(`/api/cameras/${cameraId}/start`),

    stop: (cameraId: string) =>
      post<{ status: string; running: boolean }>(`/api/cameras/${cameraId}/stop`),

    status: (cameraId: string) =>
      get<CameraStatus>(`/api/cameras/${cameraId}/status`),

    getConfig: (cameraId: string) =>
      get<CameraConfig>(`/api/cameras/${cameraId}/config`),

    updateConfig: (cameraId: string, update: ConfigUpdate) =>
      put<{ status: string }>(`/api/cameras/${cameraId}/config`, update),

    switchModel: (cameraId: string, model_name: string) =>
      post<{ status: string; model: string; restarted: boolean }>(
        `/api/cameras/${cameraId}/model`, { model_name },
      ),

    listProfiles: () =>
      get<{ profiles: string[] }>('/api/cameras/profiles'),

    loadProfile: (cameraId: string, name: string) =>
      post<{ status: string }>(`/api/cameras/${cameraId}/profiles/${encodeURIComponent(name)}/load`),
  },

  models: {
    list: () =>
      get<{ models: ModelInfo[]; models_dir: string }>('/api/models'),
  },

  webrtc: {
    offer: (cameraId: string, sdp: string, type: string) =>
      post<{ sdp: string; type: string }>(
        `/api/webrtc/${cameraId}/offer`, { sdp, type },
      ),
  },

  recordings: {
    list: () =>
      get<{ recordings: Recording[] }>('/api/recordings'),

    downloadUrl: (filename: string) =>
      `${_serverUrl}/api/recordings/${encodeURIComponent(filename)}`,

    listLogs: () =>
      get<{ logs: LogFile[] }>('/api/logs'),

    logDownloadUrl: (filename: string) =>
      `${_serverUrl}/api/logs/${encodeURIComponent(filename)}`,
  },

  system: {
    metrics: () =>
      get<SystemMetrics>('/api/system/metrics'),

    info: () =>
      get<SystemInfo>('/api/system/info'),
  },
}
