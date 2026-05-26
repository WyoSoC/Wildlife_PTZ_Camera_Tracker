import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, Play, FileText, Film, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import type { LogFile, Recording } from '../types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatBytes(mb: number) {
  return mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${mb} MB`
}

// Derive duration from filename e.g. output_20260525_143000_with_box.mp4
function filenameLabel(filename: string) {
  const m = filename.match(/output_(\d{8}_\d{6})/)
  if (!m) return filename
  const ts = m[1]
  return `${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)} ${ts.slice(9, 11)}:${ts.slice(11, 13)}`
}

export function LogsTab() {
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [logs, setLogs] = useState<LogFile[]>([])
  const [selected, setSelected] = useState<Recording | null>(null)
  const [loading, setLoading] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [recRes, logRes] = await Promise.all([
        api.recordings.list(),
        api.recordings.listLogs(),
      ])
      setRecordings(recRes.recordings)
      setLogs(logRes.logs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Load selected recording into the video element
  useEffect(() => {
    if (videoRef.current && selected) {
      videoRef.current.src = api.recordings.downloadUrl(selected.filename)
      videoRef.current.load()
    }
  }, [selected])

  return (
    <div className="h-full overflow-auto p-4">
      <div className="flex gap-4 max-w-6xl mx-auto">

        {/* ── Left: recordings ── */}
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white/60 flex items-center gap-2">
              <Film size={14} /> Recordings
            </h2>
            <Button size="sm" variant="ghost" onClick={refresh} loading={loading}>
              <RefreshCw size={11} /> Refresh
            </Button>
          </div>

          {/* Inline player */}
          {selected && (
            <Card>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-white/40">
                  <span>{filenameLabel(selected.filename)}</span>
                  <span>{formatBytes(selected.size_mb)}</span>
                </div>
                <video
                  ref={videoRef}
                  controls
                  className="w-full rounded bg-black aspect-video"
                />
              </div>
            </Card>
          )}

          {/* Recordings list */}
          <Card title={`${recordings.length} recording${recordings.length !== 1 ? 's' : ''}`}>
            {recordings.length === 0 ? (
              <p className="text-xs text-white/30 py-4 text-center">
                No recordings found in videos/with_box/
              </p>
            ) : (
              <div className="space-y-1">
                {recordings.map((rec) => {
                  const isActive = selected?.filename === rec.filename
                  return (
                    <div
                      key={rec.filename}
                      className={[
                        'flex items-center gap-2 px-2 py-2 rounded-md text-xs',
                        'border transition-colors cursor-pointer',
                        isActive
                          ? 'border-blue-600/60 bg-blue-900/20'
                          : 'border-transparent hover:border-surface-border hover:bg-surface-raised',
                      ].join(' ')}
                      onClick={() => setSelected(isActive ? null : rec)}
                    >
                      <Film size={12} className="text-white/30 shrink-0" />
                      <span className="flex-1 truncate text-white/70 font-mono">
                        {filenameLabel(rec.filename)}
                      </span>
                      <span className="text-white/30 shrink-0">{formatBytes(rec.size_mb)}</span>
                      <span className="text-white/20 shrink-0">{formatDate(rec.modified)}</span>
                      <div className="flex gap-1 shrink-0">
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelected(rec) }}
                          className="p-1 rounded hover:bg-surface-border text-white/40 hover:text-blue-400"
                          title="Play inline"
                        >
                          <Play size={11} />
                        </button>
                        <a
                          href={api.recordings.downloadUrl(rec.filename)}
                          download={rec.filename}
                          onClick={(e) => e.stopPropagation()}
                          className="p-1 rounded hover:bg-surface-border text-white/40 hover:text-green-400"
                          title="Download"
                        >
                          <Download size={11} />
                        </a>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>

        {/* ── Right: CSV logs ── */}
        <div className="w-64 shrink-0">
          <Card title={`Joystick Logs (${logs.length})`}>
            {logs.length === 0 ? (
              <p className="text-xs text-white/30 py-4 text-center">
                No CSV logs found.
              </p>
            ) : (
              <div className="space-y-1">
                {logs.map((log) => (
                  <div
                    key={log.filename}
                    className="flex items-center gap-2 px-2 py-2 rounded-md text-xs
                               border border-transparent hover:border-surface-border
                               hover:bg-surface-raised transition-colors"
                  >
                    <FileText size={12} className="text-white/30 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-white/60 font-mono">
                        {log.filename.replace('ptz_control_log_', '').replace('.csv', '')}
                      </div>
                      <div className="text-white/30 mt-0.5">
                        {log.rows.toLocaleString()} rows · {formatDate(log.modified)}
                      </div>
                    </div>
                    <a
                      href={api.recordings.logDownloadUrl(log.filename)}
                      download={log.filename}
                      className="p-1 rounded hover:bg-surface-border text-white/40
                                 hover:text-green-400 shrink-0"
                      title="Download CSV"
                    >
                      <Download size={11} />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

      </div>
    </div>
  )
}
