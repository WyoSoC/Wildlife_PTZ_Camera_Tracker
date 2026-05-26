import { useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { CameraTab } from './tabs/CameraTab'
import { ControlTab } from './tabs/ControlTab'
import { LogsTab } from './tabs/LogsTab'
import { StatusDot } from './components/ui/Badge'

type TabId = 'camera' | 'control' | 'logs'

const TABS: { id: TabId; label: string }[] = [
  { id: 'camera',  label: 'Camera & Config' },
  { id: 'control', label: 'Controls' },
  { id: 'logs',    label: 'Logs & Recordings' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('camera')
  const ws = useWebSocket()

  return (
    <div className="flex flex-col h-screen bg-surface-base text-white overflow-hidden">
      {/* ── Header ── */}
      <header className="flex items-center gap-3 px-5 py-2.5 border-b border-surface-border bg-surface-panel shrink-0">
        <span className="text-base font-bold tracking-tight select-none">
          🦅 Eagle Tracker
        </span>

        <div className="flex items-center gap-1.5 ml-2">
          <StatusDot active={ws.wsConnected} />
          <span className="text-xs text-white/40">
            {ws.wsConnected ? 'Server connected' : 'Server disconnected'}
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

        {ws.telemetry?.rec_active && (
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs font-medium text-red-400">
              REC {ws.telemetry.rec_elapsed.toFixed(0)}s / {ws.telemetry.rec_total.toFixed(0)}s
            </span>
          </div>
        )}
      </header>

      {/* ── Tab bar ── */}
      <nav className="flex shrink-0 border-b border-surface-border bg-surface-panel px-4">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              'relative px-5 py-3 text-sm font-medium transition-colors select-none',
              'border-b-2',
              activeTab === tab.id
                ? 'border-blue-500 text-white'
                : 'border-transparent text-white/40 hover:text-white/70',
            ].join(' ')}
          >
            {tab.label}
            {/* Red pulse dot on Controls tab while recording */}
            {tab.id === 'control' && ws.telemetry?.rec_active && (
              <span className="absolute top-2.5 right-2 w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            )}
          </button>
        ))}
      </nav>

      {/* ── Tab content ── */}
      <main className="flex-1 overflow-hidden">
        <div className={activeTab === 'camera'  ? 'h-full' : 'hidden'}><CameraTab /></div>
        <div className={activeTab === 'control' ? 'h-full' : 'hidden'}><ControlTab ws={ws} /></div>
        <div className={activeTab === 'logs'    ? 'h-full' : 'hidden'}><LogsTab /></div>
      </main>
    </div>
  )
}
