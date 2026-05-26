import type { CameraConfig, CameraStatus, ConfigUpdate, NDISource, Recording, LogFile } from '../types'

const BASE = ''  // same origin in prod; Vite proxy handles /api and /ws in dev

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: body != null ? { 'Content-Type': 'application/json' } : {},
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  cameras: {
    discover: () =>
      get<{ sources: NDISource[] }>('/api/cameras/discover'),

    connect: (source_match: string, source_type = 'ndi', rtsp_url?: string) =>
      post<{ status: string }>('/api/cameras/connect', {
        source_match,
        source_type,
        rtsp_url,
      }),

    disconnect: () => post<{ status: string }>('/api/cameras/disconnect'),

    start: () => post<{ status: string; running: boolean }>('/api/cameras/start'),
    stop:  () => post<{ status: string; running: boolean }>('/api/cameras/stop'),
    status: () => get<CameraStatus>('/api/cameras/status'),

    getConfig: () => get<CameraConfig>('/api/cameras/config'),

    updateConfig: (update: ConfigUpdate) =>
      put<{ status: string }>('/api/cameras/config', update),

    listProfiles: () => get<{ profiles: string[] }>('/api/cameras/profiles'),

    loadProfile: (name: string) =>
      post<{ status: string }>(`/api/cameras/profiles/${encodeURIComponent(name)}/load`),
  },

  webrtc: {
    offer: (sdp: string, type: string) =>
      post<{ sdp: string; type: string }>('/api/webrtc/offer', { sdp, type }),
  },

  recordings: {
    list: () => get<{ recordings: Recording[] }>('/api/recordings'),
    downloadUrl: (filename: string) =>
      `/api/recordings/${encodeURIComponent(filename)}`,

    listLogs: () => get<{ logs: LogFile[] }>('/api/logs'),
    logDownloadUrl: (filename: string) =>
      `/api/logs/${encodeURIComponent(filename)}`,
  },
}
