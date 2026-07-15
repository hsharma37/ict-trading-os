import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { analyticsApi } from '@/api/client'
import TradeJournal from '@/components/TradeJournal'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell
} from 'recharts'
import {
  TrendingUp, TrendingDown, DollarSign, Target, AlertTriangle, BookOpen, CheckCircle, Pencil
} from 'lucide-react'

interface Trade {
  id: string
  symbol: string
  side: string
  entry_price: number
  stop_loss: number
  take_profit_1?: number
  take_profit_2?: number
  take_profit_3?: number
  quantity: number
  initial_quantity: number
  remaining_quantity: number
  status: string
  realized_pnl: number
  unrealized_pnl: number
  total_r: number
  legs: any[]
  strategy?: string
  notes?: string
  created_at: string
  closed_at?: string
  exit_price?: number
  current_price?: number
}

export default function Analytics() {
  const [expectancy, setExpectancy] = useState<any>(null)
  const [heatmap, setHeatmap] = useState<any>(null)
  const [drawdown, setDrawdown] = useState<any>(null)
  const [kelly, setKelly] = useState<any>(null)
  const [symbols, setSymbols] = useState<any>(null)
  const [closedTrades, setClosedTrades] = useState<Trade[]>([])
  const [journalNotes, setJournalNotes] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [exp, hm, dd, kl, sym, rec] = await Promise.all([
          analyticsApi.expectancy(),
          analyticsApi.heatmap(),
          analyticsApi.drawdown(),
          analyticsApi.kelly(),
          analyticsApi.symbols(),
          analyticsApi.recent(50),
        ])
        setExpectancy(exp.data)
        setHeatmap(hm.data)
        setDrawdown(dd.data)
        setKelly(kl.data)
        setSymbols(sym.data)
        const trades = rec.data?.trades || []
        const closed = trades.filter((t: Trade) => 
          t.status === 'CLOSED' || t.status === 'closed' || 
          (t.exit_price !== undefined && t.remaining_quantity === 0)
        )
        setClosedTrades(closed)
      } catch (err: any) {
        setError(err.message || 'Failed to load analytics')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const autoJournal = (trade: Trade): string => {
    const pnl = trade.realized_pnl || 0
    const r = trade.total_r || 0
    const direction = trade.side === 'BUY' ? 'Long' : 'Short'
    const result = pnl >= 0 ? 'Win' : 'Loss'
    const setup = trade.strategy || 'No strategy tag'
    const entry = trade.entry_price
    // Use exit_price if available, otherwise last leg's exit_price, otherwise current_price
    const exit = trade.exit_price || (trade.legs?.length > 0 ? trade.legs[trade.legs.length - 1].exit_price : null) || trade.current_price || 'N/A'
    const sl = trade.stop_loss

    let reasons = []
    if (trade.legs && trade.legs.length > 0) {
      const legLabels = trade.legs.map((l: any) => `${l.label}(${Math.round(l.fraction*100)}%)`).join(', ')
      reasons.push(`Partial closes: ${legLabels}`)
    }
    if (Math.abs(r) >= 2) reasons.push('Target hit (2R+)')
    else if (Math.abs(r) >= 1) reasons.push('1R target reached')
    else if (Math.abs(r) < 0.5) reasons.push('Quick scratch / tight stop')

    // AI-like notes based on trade data
    let aiNotes = []
    if (pnl > 0 && r >= 1.5) aiNotes.push('Excellent trade management — good R multiple.')
    else if (pnl > 0 && r < 1) aiNotes.push('Small win — consider holding for higher targets.')
    else if (pnl < 0 && r > -1) aiNotes.push('Tight loss — well managed risk.')
    else if (pnl < 0 && r <= -2) aiNotes.push('Deep stop — review entry timing and SL placement.')
    if (trade.legs && trade.legs.length > 1) aiNotes.push('Scaled out nicely — good position management.')

    return `${direction} ${trade.symbol} — ${result} ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} (${r.toFixed(2)}R)
Entry: ${entry} → Exit: ${exit} | SL: ${sl}
Setup: ${setup}
${reasons.join(' | ')}

AI Notes:
${aiNotes.map(n => `- ${n}`).join('\n')}

Lessons learned:
- 
- 
- 
`
  }

  const handleAutoJournal = (trade: Trade) => {
    const entry = autoJournal(trade)
    setJournalNotes((prev) => ({ ...prev, [trade.id]: entry }))
  }

  const isPositive = (val: number) => val >= 0

  const heatmapData = heatmap?.sessions
    ? Object.entries(heatmap.sessions).map(([name, data]: [string, any]) => ({
        name,
        count: data.count || 0,
        winRate: data.win_rate || 0,
        pnl: data.pnl || 0,
      }))
    : []

  const equityData = drawdown?.equity_curve || []

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
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
          <p className="text-muted-foreground">Performance metrics and insights</p>
        </div>
        {expectancy?.source === 'mt5' ? (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live · MT5 terminal
          </span>
        ) : expectancy?.source === 'journal' ? (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
            Journal · MT5 offline (last-known closed trades)
          </span>
        ) : (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-muted border border-border text-muted-foreground">
            Internal ledger
          </span>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-center gap-2">
          <CheckCircle className="w-4 h-4" />
          {success}
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

      {/* Durable, per-instrument closed-trade journal */}
      <TradeJournal />

      {/* Auto-Journal notes (AI-generated commentary per closed trade) */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            Journal Notes (auto-generated)
          </CardTitle>
          <div className="text-sm text-muted-foreground">
            {closedTrades.length} closed trades
          </div>
        </CardHeader>
        <CardContent>
          {closedTrades.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              No closed trades yet. When you close a trade, it will appear here for journaling.
            </div>
          ) : (
            <div className="space-y-4">
              {closedTrades.map((trade) => {
                const isJournalReady = !!journalNotes[trade.id]
                return (
                  <div key={trade.id} className="border rounded-lg overflow-hidden">
                    <div className="p-3 flex items-center justify-between bg-muted/30">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                          trade.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {trade.side}
                        </span>
                        <span className="font-bold">{trade.symbol}</span>
                        <span className={`text-sm font-semibold ${isPositive(trade.realized_pnl) ? 'text-green-400' : 'text-red-400'}`}>
                          ${trade.realized_pnl?.toFixed(2)} ({trade.total_r?.toFixed(2)}R)
                        </span>
                        <span className="text-xs text-muted-foreground">{trade.strategy}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAutoJournal(trade)}
                          className="px-2 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1"
                        >
                          <Pencil className="w-3 h-3" />
                          Auto Journal
                        </button>
                      </div>
                    </div>
                    <div className="p-3 space-y-2">
                      <textarea
                        className="w-full px-3 py-2 border rounded-md bg-background text-sm min-h-[100px]"
                        placeholder="Journal entry for this trade..."
                        value={journalNotes[trade.id] || ''}
                        onChange={(e) => setJournalNotes((prev) => ({ ...prev, [trade.id]: e.target.value }))}
                      />
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">
                          Entry: {trade.entry_price} → Exit: {trade.exit_price || trade.current_price || '-'} | SL: {trade.stop_loss}
                        </span>
                        <Button
                          size="sm"
                          disabled={!isJournalReady}
                          onClick={() => {
                            // In a real app, this would save to backend
                            setSuccess(`Journal saved for ${trade.symbol} ${trade.side}`)
                            setTimeout(() => setSuccess(null), 3000)
                          }}
                        >
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Save Entry
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
