import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { analyticsApi } from '@/api/client'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell
} from 'recharts'
import {
  TrendingUp, TrendingDown, DollarSign, Target, AlertTriangle
} from 'lucide-react'

// const COLORS = ['#22c55e', '#ef4444', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899']

export default function Analytics() {
  const [expectancy, setExpectancy] = useState<any>(null)
  const [heatmap, setHeatmap] = useState<any>(null)
  const [drawdown, setDrawdown] = useState<any>(null)
  const [kelly, setKelly] = useState<any>(null)
  const [symbols, setSymbols] = useState<any>(null)
  const [recent, setRecent] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [exp, hm, dd, kl, sym, rec] = await Promise.all([
          analyticsApi.expectancy(),
          analyticsApi.heatmap(),
          analyticsApi.drawdown(),
          analyticsApi.kelly(),
          analyticsApi.symbols(),
          analyticsApi.recent(10),
        ])
        setExpectancy(exp.data)
        setHeatmap(hm.data)
        setDrawdown(dd.data)
        setKelly(kl.data)
        setSymbols(sym.data)
        setRecent(rec.data?.trades || [])
      } catch (err: any) {
        setError(err.message || 'Failed to load analytics')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const heatmapData = heatmap?.sessions
    ? Object.entries(heatmap.sessions).map(([name, data]: [string, any]) => ({
        name,
        count: data.count || 0,
        winRate: data.win_rate || 0,
        pnl: data.pnl || 0,
      }))
    : []

  const equityData = drawdown?.equity_curve || []
  /* const monthlyData = monthly?.monthly
    ? Object.entries(monthly.monthly).map(([month, data]: [string, any]) => ({
        month,
        pnl: data.pnl || 0,
        trades: data.trades || 0,
        winRate: data.win_rate || 0,
      }))
    : [] */

  const symbolData = symbols?.symbols
    ? Object.entries(symbols.symbols).map(([sym, data]: [string, any]) => ({
        symbol: sym,
        trades: data.trades || 0,
        winRate: data.win_rate || 0,
        pnl: data.total_pnl || 0,
      }))
    : []

  const winLossData = expectancy
    ? [
        { name: 'Wins', value: expectancy.win_count || 0, color: '#22c55e' },
        { name: 'Losses', value: expectancy.loss_count || 0, color: '#ef4444' },
      ]
    : []

  const isPositive = (val: number) => val >= 0

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground">Loading performance data...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground">Performance metrics and insights</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <DollarSign className="w-4 h-4" /> Expectancy
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(expectancy?.expectancy || 0) ? 'text-green-400' : 'text-red-400'}`}>
              ${(expectancy?.expectancy || 0).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">Per trade</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="w-4 h-4" /> R-Factor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(expectancy?.r_factor || 0) ? 'text-green-400' : 'text-red-400'}`}>
              {(expectancy?.r_factor || 0).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">Average R</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingDown className="w-4 h-4" /> Max Drawdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-400">
              {(drawdown?.max_drawdown || 0).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">{(drawdown?.max_drawdown_duration || 0)} trades duration</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> Win Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(expectancy?.win_rate || 0).toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">{expectancy?.total_trades || 0} trades</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Equity Curve */}
        <Card>
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
          </CardHeader>
          <CardContent>
            {equityData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={equityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="trade" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="equity" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                No equity data yet. Place some trades to see the curve.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Win/Loss Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Win/Loss Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {winLossData.length > 0 && winLossData.some(d => d.value > 0) ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={winLossData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {winLossData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                No trade data yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Session Heatmap */}
        <Card>
          <CardHeader>
            <CardTitle>Session Performance</CardTitle>
          </CardHeader>
          <CardContent>
            {heatmapData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={heatmapData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="pnl" fill="#3b82f6" name="PnL" />
                  <Bar dataKey="count" fill="#22c55e" name="Trades" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                No session data yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Kelly Criterion */}
        <Card>
          <CardHeader>
            <CardTitle>Kelly Criterion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Win Rate</span>
                <span className="font-medium">{((kelly?.win_rate || 0) * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Avg Win</span>
                <span className="font-medium text-green-400">${(kelly?.avg_win || 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Avg Loss</span>
                <span className="font-medium text-red-400">${(kelly?.avg_loss || 0).toFixed(2)}</span>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-sm text-muted-foreground">Kelly Fraction</div>
                <div className="text-2xl font-bold">{(kelly?.kelly_fraction || 0).toFixed(4)}</div>
                <div className="text-xs text-muted-foreground">Full Kelly</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-sm text-muted-foreground">Half Kelly</div>
                <div className="text-2xl font-bold">{(kelly?.kelly_half || 0).toFixed(4)}</div>
                <div className="text-xs text-muted-foreground">Recommended position size</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Symbol Performance */}
      <Card>
        <CardHeader>
          <CardTitle>Symbol Performance</CardTitle>
        </CardHeader>
        <CardContent>
          {symbolData.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {symbolData.map((s) => (
                <div key={s.symbol} className="p-3 rounded-lg border border-border bg-card">
                  <div className="font-semibold text-sm">{s.symbol}</div>
                  <div className={`text-lg font-bold ${isPositive(s.pnl) ? 'text-green-400' : 'text-red-400'}`}>
                    ${s.pnl.toFixed(2)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {s.trades} trades | {s.winRate}% win
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              No symbol data yet. Place trades across different instruments to see performance.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Trades */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Trades</CardTitle>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              No recent trades. Place trades to see history here.
            </div>
          ) : (
            <div className="space-y-2">
              {recent.map((t) => (
                <div key={t.id} className="flex items-center justify-between p-2 rounded bg-muted text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                      t.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {t.side}
                    </span>
                    <span className="font-semibold">{t.symbol}</span>
                    <span className="text-muted-foreground">{t.strategy}</span>
                  </div>
                  <div className={`font-semibold ${isPositive(t.realized_pnl) ? 'text-green-400' : 'text-red-400'}`}>
                    ${t.realized_pnl?.toFixed(2)} ({t.total_r?.toFixed(2)}R)
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
