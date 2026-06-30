import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { alertsApi } from '@/api/client'
import {
  Bell, AlertTriangle, CheckCircle, Plus, Trash2, ToggleLeft, ToggleRight,
  Zap
} from 'lucide-react'

interface Alert {
  id: string
  symbol: string
  alert_type: string
  condition: string
  threshold: number
  message: string
  is_active: boolean
  triggered_at: string | null
  created_at: string
}

const INSTRUMENTS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!']

export default function AlertManager() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [history, setHistory] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [checking, setChecking] = useState(false)

  const [newSymbol, setNewSymbol] = useState('EURUSD')
  const [newCondition, setNewCondition] = useState('above')
  const [newThreshold, setNewThreshold] = useState('')
  const [newMessage, setNewMessage] = useState('')

  const fetchAlerts = useCallback(async () => {
    try {
      const [alertsRes, historyRes] = await Promise.all([
        alertsApi.list(),
        alertsApi.history(),
      ])
      setAlerts(alertsRes.data?.alerts || [])
      setHistory(historyRes.data?.history || [])
    } catch (e: any) {
      setError(e?.message || 'Failed to load alerts')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const createAlert = async () => {
    if (!newThreshold) {
      setError('Threshold is required')
      return
    }
    setCreating(true)
    setError(null)
    try {
      await alertsApi.create({
        symbol: newSymbol,
        alert_type: 'price',
        condition: newCondition,
        threshold: parseFloat(newThreshold),
        message: newMessage || undefined,
      })
      fetchAlerts()
      setNewThreshold('')
      setNewMessage('')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create alert')
    } finally {
      setCreating(false)
    }
  }

  const deleteAlert = async (id: string) => {
    try {
      await alertsApi.delete(id)
      fetchAlerts()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to delete alert')
    }
  }

  const toggleAlert = async (id: string) => {
    try {
      await alertsApi.toggle(id)
      fetchAlerts()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to toggle alert')
    }
  }

  const checkAlerts = async () => {
    setChecking(true)
    try {
      await alertsApi.check()
      fetchAlerts()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Check failed')
    } finally {
      setChecking(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Alert Manager</h1>
        <p className="text-muted-foreground">Loading alerts...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alert Manager</h1>
          <p className="text-muted-foreground">Price alerts and trigger history</p>
        </div>
        <Button
          onClick={checkAlerts}
          disabled={checking}
          variant="outline"
          size="sm"
        >
          <Zap className={`w-4 h-4 mr-2 ${checking ? 'animate-spin' : ''}`} />
          {checking ? 'Checking...' : 'Check Now'}
        </Button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Create Alert */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Create Alert</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 items-end">
            <div className="space-y-2">
              <label className="text-xs font-medium">Symbol</label>
              <select
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value)}
                className="px-3 py-2 border rounded-md bg-background text-sm"
              >
                {INSTRUMENTS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium">Condition</label>
              <select
                value={newCondition}
                onChange={(e) => setNewCondition(e.target.value)}
                className="px-3 py-2 border rounded-md bg-background text-sm"
              >
                <option value="above">Price Above</option>
                <option value="below">Price Below</option>
                <option value="crosses_up">Crosses Up</option>
                <option value="crosses_down">Crosses Down</option>
                <option value="percent_change">% Change ≥</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium">Threshold</label>
              <input
                type="number"
                step="0.00001"
                value={newThreshold}
                onChange={(e) => setNewThreshold(e.target.value)}
                placeholder="1.1000"
                className="px-3 py-2 border rounded-md bg-background text-sm w-32"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium">Message (optional)</label>
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Alert message"
                className="px-3 py-2 border rounded-md bg-background text-sm w-40"
              />
            </div>
            <Button
              onClick={createAlert}
              disabled={creating}
              size="sm"
            >
              <Plus className="w-4 h-4 mr-2" />
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Active</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-400">
              {alerts.filter(a => a.is_active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{alerts.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Triggered</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{history.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Inactive</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {alerts.filter(a => !a.is_active && !a.triggered_at).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Alert Rules</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No alerts configured. Create one above to get started.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`flex items-center justify-between p-3 rounded-lg border ${
                    alert.is_active ? 'border-green-500/20 bg-green-500/5' : 'border-border bg-muted/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {alert.is_active ? (
                      <Bell className="w-4 h-4 text-green-400" />
                    ) : alert.triggered_at ? (
                      <CheckCircle className="w-4 h-4 text-blue-400" />
                    ) : (
                      <ToggleLeft className="w-4 h-4 text-muted-foreground" />
                    )}
                    <div>
                      <div className="font-semibold text-sm">{alert.symbol}</div>
                      <div className="text-xs text-muted-foreground">
                        {alert.condition} {alert.threshold} — {alert.message}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleAlert(alert.id)}
                      className="p-1.5 rounded hover:bg-muted"
                      title={alert.is_active ? 'Disable' : 'Enable'}
                    >
                      {alert.is_active ? (
                        <ToggleRight className="w-4 h-4 text-green-400" />
                      ) : (
                        <ToggleLeft className="w-4 h-4 text-muted-foreground" />
                      )}
                    </button>
                    <button
                      onClick={() => deleteAlert(alert.id)}
                      className="p-1.5 rounded hover:bg-red-500/10 text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Trigger History */}
      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Trigger History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {history.map((h) => (
                <div key={h.id} className="flex items-center justify-between p-3 rounded-lg bg-muted text-sm">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-4 h-4 text-blue-400" />
                    <div>
                      <span className="font-semibold">{h.symbol}</span>
                      <span className="text-muted-foreground"> — {h.message}</span>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {h.triggered_at ? new Date(h.triggered_at).toLocaleString() : '-'}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
