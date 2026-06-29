import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { apiClient } from '@/api/client'

interface AlertItem {
  id: string
  symbol: string
  alert_type: string
  condition: any
  message: string
  is_active: boolean
  triggered_at: string | null
  created_at: string
}

interface AlertHistoryItem {
  id: string
  symbol: string
  alert_type: string
  message: string
  severity: string
  triggered_at: string
}

export default function AlertManager() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [history, setHistory] = useState<AlertHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [wsStatus, setWsStatus] = useState('connecting')

  useEffect(() => {
    async function load() {
      try {
        const [alertsRes, historyRes] = await Promise.all([
          apiClient.get('/api/v1/alerts?user_id=00000000-0000-0000-0000-000000000000'),
          apiClient.get('/api/v1/alerts/history?user_id=00000000-0000-0000-0000-000000000000'),
        ])
        setAlerts(alertsRes.data || [])
        setHistory(historyRes.data || [])
      } catch (err: any) {
        setError(err.message || 'Failed to load alerts')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // WebSocket for real-time alerts
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/api/v1/ws/alerts')
    ws.onopen = () => {
      setWsStatus('connected')
      ws.send(JSON.stringify({ type: 'ping' }))
    }
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'alert') {
        // Refresh history when new alert arrives
        apiClient.get('/api/v1/alerts/history?user_id=00000000-0000-0000-0000-000000000000').then((res: any) => {
          setHistory(res.data || [])
        })
      }
    }
    ws.onclose = () => setWsStatus('disconnected')
    ws.onerror = () => setWsStatus('error')

    return () => ws.close()
  }, [])

  const statusColor = {
    connected: 'bg-green-500',
    connecting: 'bg-yellow-500',
    disconnected: 'bg-red-500',
    error: 'bg-red-500',
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Alert Manager</h1>
        <p>Loading...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alert Manager</h1>
          <p className="text-muted-foreground">Active rules and trigger history</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Live stream:</span>
          <span className={`w-2 h-2 rounded-full ${statusColor[wsStatus as keyof typeof statusColor]}`} />
          <span className="capitalize">{wsStatus}</span>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Active Rules</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {alerts.filter((a) => a.is_active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total Rules</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{alerts.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Triggers Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{history.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">WebSocket</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{wsStatus}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Alert Rules</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <p className="text-muted-foreground">No alert rules configured.</p>
          ) : (
            <div className="divide-y">
              {alerts.map((alert) => (
                <div key={alert.id} className="py-3 flex items-center justify-between">
                  <div>
                    <p className="font-medium">{alert.symbol}</p>
                    <p className="text-sm text-muted-foreground">{alert.alert_type}</p>
                  </div>
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      alert.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {alert.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Trigger History</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-muted-foreground">No alerts triggered yet.</p>
          ) : (
            <div className="divide-y">
              {history.map((h) => (
                <div key={h.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">
                      {h.symbol} — {h.alert_type}
                    </p>
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full ${
                        h.severity === 'critical'
                          ? 'bg-red-100 text-red-800'
                          : h.severity === 'warning'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {h.severity}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{h.message}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(h.triggered_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
