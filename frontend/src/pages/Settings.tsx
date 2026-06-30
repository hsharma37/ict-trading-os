import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { apiClient } from '@/api/client'
import {
  Settings, Save, RefreshCw, CheckCircle, AlertTriangle, Moon, Sun
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

const SYMBOLS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!']

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await apiClient.get('/settings')
      const data = res.data
      if (data) {
        setSettings({ ...DEFAULTS, ...data })
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [])

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
