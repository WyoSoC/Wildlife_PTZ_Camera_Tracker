import { useState } from 'react'
import type { ServerConfig } from '../types'
import { useServer } from '../context/ServerContext'
import { api, setServerConfig } from '../api/client'

const TAILSCALE_DOMAIN = 'echo-tint.ts.net'

export function ConnectScreen() {
  const { connect, savedServers } = useServer()

  const [url,     setUrl]     = useState('')
  const [name,    setName]    = useState('')
  const [apiKey,  setApiKey]  = useState('')
  const [testing, setTesting] = useState(false)
  const [status,  setStatus]  = useState<{ ok: boolean; msg: string } | null>(null)

  const normalise = (raw: string): string => {
    let u = raw.trim()
    if (!u) return u
    // Bare name (no dots, colons, or slashes) → expand to Tailscale FQDN
    if (!/[.:/]/.test(u)) {
      u = `${u}.${TAILSCALE_DOMAIN}`
    }
    if (!/^https?:\/\//i.test(u)) {
      const hostname = u.split('/')[0].split(':')[0]
      const isLocal =
        hostname === 'localhost' ||
        hostname === '0.0.0.0'  ||
        /^127\./.test(hostname) ||
        /^10\./.test(hostname)  ||
        /^192\.168\./.test(hostname) ||
        /^172\.(1[6-9]|2\d|3[01])\./.test(hostname) ||
        /^100\./.test(hostname)
      u = (isLocal ? 'http://' : 'https://') + u
    }
    return u.replace(/\/$/, '')
  }

  const resolvedUrl = normalise(url)

  const testConnection = async () => {
    const u = normalise(url)
    if (!u) return
    setTesting(true)
    setStatus(null)
    try {
      setServerConfig(u, apiKey)
      await api.system.info()
      setStatus({ ok: true, msg: 'Connection successful' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setStatus({ ok: false, msg: `Failed: ${msg}` })
    } finally {
      setTesting(false)
    }
  }

  const handleConnect = () => {
    const u = normalise(url)
    if (!u) return
    const cfg: ServerConfig = {
      url:    u,
      name:   name.trim() || new URL(u).hostname,
      apiKey: apiKey.trim(),
    }
    connect(cfg)
  }

  const quickConnect = (cfg: ServerConfig) => connect(cfg)

  return (
    <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center px-4">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="text-5xl mb-3">🦅</div>
        <h1 className="text-2xl font-bold text-white">Wildlife PTZ Camera Tracker</h1>
        <p className="text-white/40 text-sm mt-1">Connect to an edge server to begin</p>
      </div>

      {/* Connect form */}
      <div className="w-full max-w-md bg-surface-panel border border-surface-border rounded-xl p-6 space-y-4">
        <h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider">
          New Connection
        </h2>

        <div className="space-y-2">
          <label className="text-xs text-white/50">Server</label>
          <input
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleConnect()}
            placeholder="cortex"
            className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2
                       text-sm text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
          />
          {url.trim() && (
            <p className="text-xs text-white/40 font-mono truncate">
              → {resolvedUrl}
            </p>
          )}
          <p className="text-xs text-white/30">
            Enter a machine name (e.g. <code className="text-white/50">cortex</code>) or a full address.
            Local addresses use <code className="text-white/50">http://</code> automatically.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-xs text-white/50">Display Name <span className="text-white/25">(optional)</span></label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="My Edge Server"
            className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2
                       text-sm text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs text-white/50">API Key <span className="text-white/25">(leave blank if not set)</span></label>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="••••••••"
            className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2
                       text-sm text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
          />
        </div>

        {status && (
          <p className={`text-xs ${status.ok ? 'text-green-400' : 'text-red-400'}`}>
            {status.msg}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <button
            onClick={testConnection}
            disabled={!url.trim() || testing}
            className="flex-1 px-4 py-2 text-sm bg-surface-base border border-surface-border
                       rounded-lg text-white/60 hover:text-white hover:border-white/30
                       disabled:opacity-40 transition-colors"
          >
            {testing ? 'Testing…' : 'Test Connection'}
          </button>
          <button
            onClick={handleConnect}
            disabled={!url.trim()}
            className="flex-1 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500
                       rounded-lg text-white font-medium disabled:opacity-40 transition-colors"
          >
            Connect
          </button>
        </div>
      </div>

      {/* Saved servers */}
      {savedServers.length > 0 && (
        <div className="w-full max-w-md mt-5">
          <h2 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2 px-1">
            Recent servers
          </h2>
          <div className="space-y-1.5">
            {savedServers.map(cfg => (
              <div
                key={cfg.url}
                className="flex items-center justify-between bg-surface-panel border border-surface-border
                           rounded-lg px-4 py-2.5"
              >
                <div>
                  <p className="text-sm text-white font-medium">{cfg.name}</p>
                  <p className="text-xs text-white/35 truncate max-w-xs">{cfg.url}</p>
                </div>
                <button
                  onClick={() => quickConnect(cfg)}
                  className="ml-4 px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500
                             rounded-md text-white transition-colors shrink-0"
                >
                  Connect
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-8 text-xs text-white/20">
        For HTTPS access over Tailscale, run{' '}
        <code className="text-white/35">tailscale serve --bg http://localhost:PORT</code>{' '}
        on the edge server, then connect using the Tailscale hostname.
      </p>
    </div>
  )
}
