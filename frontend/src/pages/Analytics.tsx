import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { apiClient } from '@/api/client'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts'

type ExpectancyData = {
  expectancy: number
  win_rate: number
  avg_win: number
  avg_loss: number
  total_trades: number
  win_count: number
  loss_count: number
  r_factor: number
}

type HeatmapData = {
  sessions: Record<string, { count: number; wins: number; losses: number; pnl: number; win_rate: number }>
}

type DrawdownData = {
  max_drawdown: number
  max_drawdown_duration: number
  equity_curve: { trade: number; equity: number }[]
}

export default function Analytics() {
  const [expectancy, setExpectancy] = useState<ExpectancyData | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null)
  const [drawdown, setDrawdown] = useState<DrawdownData | null>(null)
  const [kelly, setKelly] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [exp, hm, dd, kl] = await Promise.all([
          apiClient.get('/api/v1/analytics/expectancy'),
          apiClient.get('/api/v1/analytics/heatmap'),
          apiClient.get('/api/v1/analytics/drawdown'),
          apiClient.get('/api/v1/analytics/kelly'),
        ])
        setExpectancy(exp.data)
        setHeatmap(hm.data)
        setDrawdown(dd.data)
        setKelly(kl.data)
      } catch (err: any) {
        setError(err.message || 'Failed to load analytics')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const heatmapChartData = heatmap?.sessions
    ? Object.entries(heatmap.sessions).map(([name, data]) => ({
        name,
        count: data.count,
        winRate: Math.round(data.win_rate * 100),
        pnl: Math.round(data.pnl * 100) / 100,
      }))
    : []

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p>Loading analytics...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <div className="text-red-500">{error}</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground">Performance metrics and insights</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Expectancy</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${expectancy?.expectancy.toFixed(2) ?? '0.00'}</div>
            <p className="text-xs text-muted-foreground">Per trade</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">R-Factor</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{expectancy?.r_factor.toFixed(2) ?? '0.0'}</div>
            <p className="text-xs text-muted-foreground">Average R</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Max Drawdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{drawdown?.max_drawdown.toFixed(2) ?? '0.0'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Win Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{expectancy?.win_rate.toFixed(1) ?? '0.0'}%</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Session Heatmap</CardTitle>
          </CardHeader>
          <CardContent>
            {heatmapChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={heatmapChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#111" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                No session data yet
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Kelly Criterion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Win Rate</span>
                <span className="font-medium">{((kelly?.win_rate ?? 0) * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Win</span>
                <span className="font-medium">${kelly?.avg_win?.toFixed(2) ?? '0.00'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Loss</span>
                <span className="font-medium">${kelly?.avg_loss?.toFixed(2) ?? '0.00'}</span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="font-medium">Kelly Fraction</span>
                <span className="font-bold">{(kelly?.kelly_fraction ?? 0).toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Half Kelly</span>
                <span className="font-bold">{(kelly?.kelly_half ?? 0).toFixed(4)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Equity Curve</CardTitle>
        </CardHeader>
        <CardContent>
          {drawdown?.equity_curve && drawdown.equity_curve.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={drawdown.equity_curve}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="trade" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="equity" stroke="#111" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground">
              No equity data yet
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
