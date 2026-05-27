import {
  createContext, useCallback, useContext, useEffect, useState,
} from 'react'
import type { CameraListItem, ServerConfig } from '../types'
import { api, setServerConfig } from '../api/client'

const LS_SERVERS    = 'wildlife-tracker-servers'
const LS_ACTIVE_URL = 'wildlife-tracker-active-url'

interface ServerContextValue {
  // null  = not connected yet  (ConnectScreen is shown)
  server:            ServerConfig | null
  cameras:           CameraListItem[]
  activeCameraId:    string | null
  savedServers:      ServerConfig[]
  connect:           (cfg: ServerConfig) => void
  disconnect:        () => void
  setActiveCameraId: (id: string) => void
  refreshCameras:    () => Promise<void>
}

const ServerContext = createContext<ServerContextValue>({
  server:            null,
  cameras:           [],
  activeCameraId:    null,
  savedServers:      [],
  connect:           () => {},
  disconnect:        () => {},
  setActiveCameraId: () => {},
  refreshCameras:    async () => {},
})

export function useServer(): ServerContextValue {
  return useContext(ServerContext)
}

export function ServerProvider({ children }: { children: React.ReactNode }) {
  const [server,         setServer]         = useState<ServerConfig | null>(null)
  const [cameras,        setCameras]        = useState<CameraListItem[]>([])
  const [activeCameraId, setActiveCameraId] = useState<string | null>(null)
  const [savedServers,   setSavedServers]   = useState<ServerConfig[]>(() => {
    try { return JSON.parse(localStorage.getItem(LS_SERVERS) || '[]') }
    catch { return [] }
  })

  const refreshCameras = useCallback(async () => {
    try {
      const { cameras: list } = await api.cameras.list()
      setCameras(list)
      if (list.length > 0 && !activeCameraId) {
        setActiveCameraId(list[0].camera_id)
      }
    } catch { /* silently skip if server unreachable */ }
  }, [activeCameraId])

  const connect = useCallback((cfg: ServerConfig) => {
    setServerConfig(cfg.url, cfg.apiKey)
    setServer(cfg)
    localStorage.setItem(LS_ACTIVE_URL, cfg.url)

    // Persist to saved-servers list (no duplicates by URL)
    setSavedServers(prev => {
      const next = [cfg, ...prev.filter(s => s.url !== cfg.url)].slice(0, 8)
      localStorage.setItem(LS_SERVERS, JSON.stringify(next))
      return next
    })
  }, [])

  const disconnect = useCallback(() => {
    setServerConfig('', '')
    setServer(null)
    setCameras([])
    setActiveCameraId(null)
    localStorage.removeItem(LS_ACTIVE_URL)
  }, [])

  // Auto-reconnect to last server on page load
  useEffect(() => {
    const lastUrl = localStorage.getItem(LS_ACTIVE_URL)
    if (!lastUrl) return
    const saved = savedServers.find(s => s.url === lastUrl)
    if (saved) connect(saved)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Poll camera list every 3 s while connected
  useEffect(() => {
    if (!server) return
    refreshCameras()
    const id = setInterval(refreshCameras, 3000)
    return () => clearInterval(id)
  }, [server, refreshCameras])

  return (
    <ServerContext.Provider value={{
      server, cameras, activeCameraId, savedServers,
      connect, disconnect, setActiveCameraId, refreshCameras,
    }}>
      {children}
    </ServerContext.Provider>
  )
}
