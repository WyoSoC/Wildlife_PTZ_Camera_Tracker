import { useState } from 'react'
import { LogOut } from 'lucide-react'
import { ServerProvider, useServer } from './context/ServerContext'
import { ConnectScreen } from './components/ConnectScreen'
import { useWebSocket } from './hooks/useWebSocket'
import { CameraTab } from './tabs/CameraTab'
import { ControlTab } from './tabs/ControlTab'
import { LogsTab } from './tabs/LogsTab'
import { ServerTab } from './tabs/ServerTab'
import { StatusDot } from './components/ui/Badge'

type TabId = 'camera' | 'control' | 'logs' | 'server'

const TABS: { id: TabId; label: string }[] = [
  { id: 'camera',  label: 'Cameras & Config' },
  { id: 'control', label: 'Controls' },
  { id: 'logs',    label: 'Logs & Recordings' },
  { id: 'server',  label: 'Server' },
]

function AppShell() {
  const { server, probing, cameras, activeCameraId, setActiveCameraId, disconnect } = useServer()
  const [activeTab, setActiveTab] = useState<TabId>('camera')
  const ws = useWebSocket(activeCameraId)

  if (probing) return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center">
      <p className="text-white/30 text-sm animate-pulse">Connecting…</p>
    </div>
  )
  if (!server) return <ConnectScreen />

  return (
    <div className="flex flex-col h-screen bg-surface-base text-white overflow-hidden">

      {/* ── Header ── */}
      <header className="flex items-center gap-3 px-5 py-2.5 border-b border-surface-border bg-surface-panel shrink-0">
        <span className="text-base font-bold tracking-tight select-none">
          🦅 Wildlife PTZ Camera Tracker
        </span>

        {/* Camera selector */}
        {cameras.length > 0 && (
          <select
            value={activeCameraId ?? ''}
            onChange={e => setActiveCameraId(e.target.value)}
            className="ml-2 text-xs bg-surface-base border border-surface-border rounded
                       px-2 py-1 text-white focus:outline-none focus:border-blue-500"
          >
            {cameras.map(c => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.camera_id}{c.source_name ? ` — ${c.source_name}` : ''}
              </option>
            ))}
          </select>
        )}

        {/* WS status */}
        <div className="flex items-center gap-1.5 ml-2">
          <StatusDot active={ws.wsConnected} />
          <span className="text-xs text-white/40">
            {ws.wsConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {ws.telemetry?.connected && (
          <div className="flex items-center gap-1.5">
            <span className="text-white/20">·</span>
            <StatusDot active />
            <span className="text-xs text-white/40 truncate max-w-40">
              {ws.telemetry.source_name}
            </span>
          </div>
        )}

        <div className="ml-auto flex items-center gap-3">
          {ws.telemetry?.rec_active && (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs font-medium text-red-400">
                REC {ws.telemetry.rec_elapsed.toFixed(0)}s / {ws.telemetry.rec_total.toFixed(0)}s
              </span>
            </div>
          )}
          <button
            onClick={disconnect}
            title={`Switch server (currently: ${server?.url})`}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-white/35
                       hover:text-white/70 hover:bg-surface-raised border border-transparent
                       hover:border-surface-border transition-colors"
          >
            <LogOut size={12} />
            {server?.name ?? 'Switch Server'}
          </button>
        </div>
      </header>

      {/* ── Tab bar ── */}
      <nav className="flex shrink-0 border-b border-surface-border bg-surface-panel px-4">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              'relative px-5 py-3 text-sm font-medium transition-colors select-none border-b-2',
              activeTab === tab.id
                ? 'border-blue-500 text-white'
                : 'border-transparent text-white/40 hover:text-white/70',
            ].join(' ')}
          >
            {tab.label}
            {tab.id === 'control' && ws.telemetry?.rec_active && (
              <span className="absolute top-2.5 right-2 w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            )}
          </button>
        ))}
      </nav>

      {/* ── Tab content ── */}
      <main className="flex-1 overflow-hidden">
        <div className={activeTab === 'camera'  ? 'h-full' : 'hidden'}><CameraTab /></div>
        <div className={activeTab === 'control' ? 'h-full' : 'hidden'}>
          <ControlTab ws={ws} cameraId={activeCameraId} />
        </div>
        <div className={activeTab === 'logs'   ? 'h-full' : 'hidden'}><LogsTab /></div>
        <div className={activeTab === 'server' ? 'h-full' : 'hidden'}><ServerTab /></div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <ServerProvider>
      <AppShell />
    </ServerProvider>
  )
}
