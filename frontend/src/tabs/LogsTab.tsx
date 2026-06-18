import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Download, Play, FileText, Film, RefreshCw,
  Trash2, RotateCcw, AlertTriangle,
} from 'lucide-react'
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
  return mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${mb.toFixed(1)} MB`
}

function filenameLabel(filename: string) {
  const m = filename.match(/output_(\d{8}_\d{6})/)
  if (!m) return filename
  const ts = m[1]
  return `${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)}  ${ts.slice(9, 11)}:${ts.slice(11, 13)}`
}

export function LogsTab() {
  const [recordings,    setRecordings]    = useState<Recording[]>([])
  const [binRecordings, setBinRecordings] = useState<Recording[]>([])
  const [logs,          setLogs]          = useState<LogFile[]>([])
  const [selected,      setSelected]      = useState<Recording | null>(null)
  const [loading,       setLoading]       = useState(false)

  // Inline confirmation state
  const [pendingDelete,    setPendingDelete]    = useState<string | null>(null)
  const [confirmEmptyBin,  setConfirmEmptyBin]  = useState(false)
  const [busyFile,         setBusyFile]         = useState<string | null>(null)

  const videoRef = useRef<HTMLVideoElement>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [recRes, binRes, logRes] = await Promise.all([
        api.recordings.list(),
        api.recordings.listBin(),
        api.recordings.listLogs(),
      ])
      setRecordings(recRes.recordings)
      setBinRecordings(binRes.recordings)
      setLogs(logRes.logs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (videoRef.current && selected) {
      videoRef.current.src = api.recordings.downloadUrl(selected.filename)
      videoRef.current.load()
    }
  }, [selected])

  const handleSoftDelete = useCallback(async (filename: string) => {
    setBusyFile(filename)
    try {
      await api.recordings.softDelete(filename)
      if (selected?.filename === filename) setSelected(null)
      setPendingDelete(null)
      await refresh()
    } catch (e) {
      console.error(e)
    } finally {
      setBusyFile(null)
    }
  }, [refresh, selected])

  const handleRestore = useCallback(async (filename: string) => {
    setBusyFile(filename)
    try {
      await api.recordings.restore(filename)
      await refresh()
    } catch (e) {
      console.error(e)
    } finally {
      setBusyFile(null)
    }
  }, [refresh])

  const handleEmptyBin = useCallback(async () => {
    setBusyFile('__bin__')
    try {
      await api.recordings.emptyBin()
      setConfirmEmptyBin(false)
      await refresh()
    } catch (e) {
      console.error(e)
    } finally {
      setBusyFile(null)
    }
  }, [refresh])

  const binTotal = binRecordings.reduce((s, r) => s + r.size_mb, 0)

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
                <video ref={videoRef} controls className="w-full rounded bg-black aspect-video" />
              </div>
            </Card>
          )}

          {/* Active recordings list */}
          <Card title={`${recordings.length} recording${recordings.length !== 1 ? 's' : ''}`}>
            {recordings.length === 0 ? (
              <p className="text-xs text-white/30 py-4 text-center">
                No recordings found in videos/with_box/
              </p>
            ) : (
              <div className="space-y-1">
                {recordings.map((rec) => {
                  const isActive  = selected?.filename === rec.filename
                  const isPending = pendingDelete === rec.filename
                  const isBusy    = busyFile === rec.filename

                  if (isPending) {
                    return (
                      <div key={rec.filename}
                        className="flex items-center gap-2 px-3 py-2.5 rounded-md text-xs
                                   border border-amber-700/60 bg-amber-900/20">
                        <AlertTriangle size={13} className="text-amber-400 shrink-0" />
                        <span className="flex-1 text-amber-200/80 truncate">
                          Move <span className="font-mono">{filenameLabel(rec.filename)}</span> to Recycle Bin?
                        </span>
                        <button
                          onClick={() => setPendingDelete(null)}
                          className="px-2 py-0.5 rounded text-white/50 hover:text-white
                                     border border-surface-border bg-surface-raised transition-colors">
                          Cancel
                        </button>
                        <button
                          disabled={isBusy}
                          onClick={() => handleSoftDelete(rec.filename)}
                          className="px-2 py-0.5 rounded text-amber-100 border border-amber-600
                                     bg-amber-700/50 hover:bg-amber-700 disabled:opacity-50 transition-colors">
                          {isBusy ? 'Moving…' : 'Move to Bin'}
                        </button>
                      </div>
                    )
                  }

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
                      <span className="text-white/20 shrink-0 hidden sm:inline">{formatDate(rec.modified)}</span>
                      <div className="flex gap-0.5 shrink-0" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => setSelected(rec)}
                          className="p-1 rounded hover:bg-surface-border text-white/40 hover:text-blue-400"
                          title="Play">
                          <Play size={11} />
                        </button>
                        <a
                          href={api.recordings.downloadUrl(rec.filename)}
                          download={rec.filename}
                          className="p-1 rounded hover:bg-surface-border text-white/40 hover:text-green-400"
                          title="Download">
                          <Download size={11} />
                        </a>
                        <button
                          onClick={() => setPendingDelete(rec.filename)}
                          className="p-1 rounded hover:bg-surface-border text-white/40 hover:text-amber-400"
                          title="Move to Recycle Bin">
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* Recycle Bin */}
          <Card>
            <div className="space-y-2">
              {/* Bin header */}
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
                  <Trash2 size={12} />
                  Recycle Bin
                  {binRecordings.length > 0 && (
                    <span className="text-white/25 font-normal normal-case tracking-normal">
                      ({binRecordings.length} · {formatBytes(binTotal)})
                    </span>
                  )}
                </span>

                {/* Empty bin — inline confirm */}
                {binRecordings.length > 0 && !confirmEmptyBin && (
                  <button
                    onClick={() => setConfirmEmptyBin(true)}
                    className="text-xs text-white/30 hover:text-red-400 flex items-center gap-1 transition-colors">
                    <Trash2 size={11} /> Empty Bin
                  </button>
                )}
                {confirmEmptyBin && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-red-300/80 flex items-center gap-1">
                      <AlertTriangle size={11} className="text-red-400" />
                      Permanently delete {binRecordings.length} file{binRecordings.length !== 1 ? 's' : ''}?
                    </span>
                    <button
                      onClick={() => setConfirmEmptyBin(false)}
                      className="text-xs text-white/40 hover:text-white transition-colors">
                      Cancel
                    </button>
                    <button
                      disabled={busyFile === '__bin__'}
                      onClick={handleEmptyBin}
                      className="text-xs px-2 py-0.5 rounded bg-red-700/60 hover:bg-red-700
                                 text-red-100 border border-red-600 disabled:opacity-50 transition-colors">
                      {busyFile === '__bin__' ? 'Deleting…' : 'Delete All'}
                    </button>
                  </div>
                )}
              </div>

              {/* Bin contents */}
              {binRecordings.length === 0 ? (
                <p className="text-xs text-white/20 py-2 text-center">Recycle bin is empty</p>
              ) : (
                <div className="space-y-1">
                  {binRecordings.map((rec) => {
                    const isBusy = busyFile === rec.filename
                    return (
                      <div key={rec.filename}
                        className="flex items-center gap-2 px-2 py-2 rounded-md text-xs
                                   border border-transparent hover:border-surface-border
                                   hover:bg-surface-raised transition-colors">
                        <Film size={12} className="text-white/20 shrink-0" />
                        <span className="flex-1 truncate text-white/40 font-mono">
                          {filenameLabel(rec.filename)}
                        </span>
                        <span className="text-white/20 shrink-0">{formatBytes(rec.size_mb)}</span>
                        <span className="text-white/15 shrink-0 hidden sm:inline">{formatDate(rec.modified)}</span>
                        <button
                          disabled={isBusy}
                          onClick={() => handleRestore(rec.filename)}
                          className="flex items-center gap-1 px-2 py-0.5 rounded text-xs
                                     text-white/40 hover:text-green-300 border border-surface-border
                                     hover:border-green-700/60 hover:bg-green-900/20
                                     disabled:opacity-50 transition-colors shrink-0">
                          <RotateCcw size={10} />
                          {isBusy ? 'Restoring…' : 'Restore'}
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* ── Right: CSV logs ── */}
        <div className="w-64 shrink-0">
          <Card title={`Joystick Logs (${logs.length})`}>
            {logs.length === 0 ? (
              <p className="text-xs text-white/30 py-4 text-center">No CSV logs found.</p>
            ) : (
              <div className="space-y-1">
                {logs.map((log) => (
                  <div key={log.filename}
                    className="flex items-center gap-2 px-2 py-2 rounded-md text-xs
                               border border-transparent hover:border-surface-border
                               hover:bg-surface-raised transition-colors">
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
                      title="Download CSV">
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
