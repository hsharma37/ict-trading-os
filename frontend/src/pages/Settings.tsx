import { useState, useEffect, useCallback } from 'react'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { apiClient } from '@/api/client'
import {
  Settings, Save, RefreshCw, CheckCircle, AlertTriangle, Moon, Sun, Radio, Wifi, WifiOff
} from 'lucide-react'

interface AppSettings {
  theme: string
  default_symbol: string
  risk_pct: number
  account_balance: number
  auto_trade: boolean
  notifications: boolean
  layout: string
}

const DEFAULTS: AppSettings = {
  theme: 'dark',
  default_symbol: 'EURUSD',
  risk_pct: 1.0,
  account_balance: 10000.0,
  auto_trade: false,
  notifications: true,
  layout: 'default',
}

const SYMBOLS = SUPPORTED_SYMBOLS

interface BridgeConfig {
  mt5_bridge_url: string
  mt5_bridge_url_source: 'override' | 'env'
  mt5_bridge_env_url: string
}

interface BridgeTestResult {
  reachable: boolean
  mt5_connected: boolean | null
  error: string | null
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // MT5 bridge URL — editable at runtime so a new tunnel URL takes effect
  // without a Vercel env change or redeploy.
  const [bridge, setBridge] = useState<BridgeConfig | null>(null)
  const [bridgeUrl, setBridgeUrl] = useState('')
  const [bridgeSaving, setBridgeSaving] = useState(false)
  const [bridgeResult, setBridgeResult] = useState<BridgeTestResult | null>(null)

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await apiClient.get('/settings')
      const data = res.data
      if (data) {
        setSettings({ ...DEFAULTS, ...data })
        if (data.mt5_bridge_url !== undefined) {
          setBridge({
            mt5_bridge_url: data.mt5_bridge_url || '',
            mt5_bridge_url_source: data.mt5_bridge_url_source || 'env',
            mt5_bridge_env_url: data.mt5_bridge_env_url || '',
          })
          setBridgeUrl(data.mt5_bridge_url || '')
        }
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [])

  const saveBridgeUrl = async () => {
    try {
      setBridgeSaving(true)
      setBridgeResult(null)
      const res = await apiClient.post('/settings/mt5-bridge-url', { url: bridgeUrl.trim() })
      const data = res.data || {}
      setBridge({
        mt5_bridge_url: data.mt5_bridge_url || '',
        mt5_bridge_url_source: data.mt5_bridge_url_source || 'env',
        mt5_bridge_env_url: data.mt5_bridge_env_url || '',
      })
      setBridgeUrl(data.mt5_bridge_url || '')
      setBridgeResult({
        reachable: !!data.reachable,
        mt5_connected: data.mt5_connected ?? null,
        error: data.error ?? null,
      })
    } catch (e: any) {
      setBridgeResult({ reachable: false, mt5_connected: null, error: e?.message || 'Failed to save bridge URL' })
    } finally {
      setBridgeSaving(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  const updateField = <K extends keyof AppSettings>(field: K, value: AppSettings[K]) => {
    setSettings((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
  }

  const saveSettings = async () => {
    try {
      setSaving(true)
      setError(null)
      await apiClient.post('/settings', settings)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e: any) {
      setError(e?.message || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Settings className="w-6 h-6 text-primary" />
            Settings
          </h1>
          <p className="text-muted-foreground">Configure your trading environment</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadSettings} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Reload
          </Button>
          <Button size="sm" onClick={saveSettings} disabled={saving}>
            {saving ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
            Save
          </Button>
          {saved && (
            <span className="text-emerald-400 text-sm flex items-center gap-1">
              <CheckCircle className="w-4 h-4" /> Saved
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* Trading Preferences */}
        <Card>
          <CardHeader>
            <CardTitle>Trading Preferences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Default Symbol</label>
              <select
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                value={settings.default_symbol}
                onChange={(e) => updateField('default_symbol', e.target.value)}
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Default Risk %</label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="10"
                value={settings.risk_pct}
                onChange={(e) => updateField('risk_pct', parseFloat(e.target.value))}
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Account Balance ($)</label>
              <input
                type="number"
                step="100"
                min="0"
                value={settings.account_balance}
                onChange={(e) => updateField('account_balance', parseFloat(e.target.value))}
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
          </CardContent>
        </Card>

        {/* Appearance */}
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Theme</label>
              <div className="flex gap-2">
                <button
                  onClick={() => updateField('theme', 'dark')}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
                    settings.theme === 'dark'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Moon className="w-4 h-4" /> Dark
                </button>
                <button
                  onClick={() => updateField('theme', 'light')}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
                    settings.theme === 'light'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Sun className="w-4 h-4" /> Light
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Layout</label>
              <select
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                value={settings.layout}
                onChange={(e) => updateField('layout', e.target.value)}
              >
                <option value="default">Default</option>
                <option value="compact">Compact</option>
                <option value="wide">Wide</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Automation */}
        <Card>
          <CardHeader>
            <CardTitle>Automation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-md bg-muted border border-border">
              <div>
                <div className="text-sm font-medium">Auto Trade</div>
                <div className="text-xs text-muted-foreground">Execute signals automatically</div>
              </div>
              <button
                onClick={() => updateField('auto_trade', !settings.auto_trade)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  settings.auto_trade ? 'bg-primary' : 'bg-muted-foreground/30'
                }`}
              >
                <span
                  className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                    settings.auto_trade ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
            <div className="flex items-center justify-between p-3 rounded-md bg-muted border border-border">
              <div>
                <div className="text-sm font-medium">Notifications</div>
                <div className="text-xs text-muted-foreground">Browser alerts for signals</div>
              </div>
              <button
                onClick={() => updateField('notifications', !settings.notifications)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  settings.notifications ? 'bg-primary' : 'bg-muted-foreground/30'
                }`}
              >
                <span
                  className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                    settings.notifications ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>

        {/* MT5 Bridge — runtime-editable tunnel URL */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-primary" />
              MT5 Bridge Connection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              The Cloudflare quick-tunnel URL changes every time the bridge restarts.
              Paste the new <span className="font-mono">https://…trycloudflare.com</span> URL
              here — it takes effect immediately, no redeploy needed. Leave blank to fall back
              to the deployed <span className="font-mono">MT5_BRIDGE_URL</span> env var.
            </p>
            <div className="space-y-2">
              <label className="text-sm font-medium">Bridge URL</label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="url"
                  placeholder="https://your-tunnel.trycloudflare.com"
                  value={bridgeUrl}
                  onChange={(e) => { setBridgeUrl(e.target.value); setBridgeResult(null) }}
                  className="flex-1 px-3 py-2 border rounded-md bg-background text-sm font-mono"
                />
                <Button size="sm" onClick={saveBridgeUrl} disabled={bridgeSaving}>
                  {bridgeSaving
                    ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                    : <Save className="w-4 h-4 mr-1" />}
                  Save &amp; Test
                </Button>
              </div>
            </div>

            {bridge && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                <span className="text-muted-foreground">
                  Source:{' '}
                  <span className={bridge.mt5_bridge_url_source === 'override' ? 'text-primary font-medium' : 'font-medium'}>
                    {bridge.mt5_bridge_url_source === 'override' ? 'Custom (this field)' : 'Env var (deployed)'}
                  </span>
                </span>
                {bridge.mt5_bridge_env_url && (
                  <span className="text-muted-foreground">
                    Env default: <span className="font-mono">{bridge.mt5_bridge_env_url}</span>
                  </span>
                )}
              </div>
            )}

            {bridgeResult && (
              <div
                className={`p-3 rounded-lg border text-sm flex items-center gap-2 ${
                  bridgeResult.reachable
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-red-500/10 border-red-500/20 text-red-400'
                }`}
              >
                {bridgeResult.reachable ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                {bridgeResult.reachable ? (
                  <span>
                    Bridge reachable
                    {bridgeResult.mt5_connected === true && ' · MT5 terminal connected'}
                    {bridgeResult.mt5_connected === false && ' · but MT5 terminal NOT connected'}
                  </span>
                ) : (
                  <span>Not reachable{bridgeResult.error ? ` — ${bridgeResult.error}` : ''}</span>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info */}
        <Card>
          <CardHeader>
            <CardTitle>System Info</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">App Version</span>
              <span className="font-mono">9.1.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Database</span>
              <span className="font-mono text-emerald-400">SQLite</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Auth</span>
              <span className="font-mono">API Key (optional)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Data Provider</span>
              <span className="font-mono">Yahoo Finance</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
