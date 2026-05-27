import { useCallback, useEffect, useRef, useState } from 'react'
import type { Telemetry, WebSocketHook } from '../types'
import { wsUrl } from '../api/client'

const RECONNECT_DELAY_MS = 2000

export function useWebSocket(cameraId: string | null): WebSocketHook {
  const wsRef          = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const [telemetry,   setTelemetry]   = useState<Telemetry | null>(null)
  const [wsConnected, setWsConnected] = useState(false)

  const connect = useCallback(() => {
    if (!cameraId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const url = wsUrl(`/ws/ptz/${cameraId}`)
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      clearTimeout(reconnectTimer.current)
    }

    ws.onclose = () => {
      setWsConnected(false)
      wsRef.current = null
      if (cameraId) {
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => ws.close()

    ws.onmessage = (e: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(e.data) as { type: string } & Telemetry
        if (msg.type === 'telemetry') setTelemetry(msg)
      } catch { /* malformed — ignore */ }
    }
  }, [cameraId])

  useEffect(() => {
    clearTimeout(reconnectTimer.current)
    wsRef.current?.close()
    wsRef.current = null
    setWsConnected(false)
    setTelemetry(null)

    if (cameraId) connect()

    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [cameraId, connect])

  const send = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return {
    telemetry,
    wsConnected,
    sendPanTilt:   useCallback((pan, tilt) => send({ type: 'pan_tilt', pan, tilt }), [send]),
    sendZoom:      useCallback((speed)     => send({ type: 'zoom', speed }),          [send]),
    sendStop:      useCallback(()          => send({ type: 'stop' }),                 [send]),
    sendAutofocus: useCallback(()          => send({ type: 'autofocus' }),            [send]),
    setMode:       useCallback((mode)      => send({ type: 'mode', mode }),           [send]),
    setRecording:  useCallback((action)    => send({ type: 'record', action }),       [send]),
  }
}
