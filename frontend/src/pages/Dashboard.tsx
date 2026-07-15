import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import {
  TrendingUp, DollarSign, Activity, Target, AlertTriangle, Newspaper, BarChart3
} from 'lucide-react'
import { tradesApi, researchApi, newsApi } from '@/api/client'
import { useMt5 } from '@/hooks/useMt5'
import Mt5PositionsPanel from '@/components/Mt5PositionsPanel'

interface TradeStats {
  total_trades: number
  open_trades: number
  closed_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  avg_pnl: number
  avg_r: number
  total_r: number
  r_tracked_trades?: number
  best_trade: number
  worst_trade: number
  max_drawdown: number
  max_win_streak: number
  max_loss_streak: number
  current_streak: number
  source?: string
}

interface MarketMover {
  symbol: string
  change_pct: number
  trend: string
  sentiment: string
}

interface Instrument {
  symbol: string
  label: string
  current_price: number
  change_pct: number
  trend: string
  sentiment: string
}

interface NewsItem {
  title: string
  source: string
  impact: string
  symbols: string[]
  reason: string
  relevant: boolean
  timestamp: string
  summary: string
  link: string
}

function relativeTime(ts: string): string {
  const diffMs = Date.now() - new Date(ts).getTime()
  if (isNaN(diffMs)) return ''
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

export default function Dashboard() {
  const [stats, setStats] = useState<TradeStats | null>(null)
  const [movers, setMovers] = useState<MarketMover[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [openTrades, setOpenTrades] = useState<any[]>([])
  const [news, setNews] = useState<NewsItem[]>([])
  const [newsFilter, setNewsFilter] = useState('All')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mt5 = useMt5()

  const loadData = useCallback(async () => {
    try {
      setError(null)
      const [statsRes, researchRes, openRes, newsRes] = await Promise.all([
        tradesApi.stats(),
        researchApi.summary(),
        tradesApi.open(),
        newsApi.latest(),
      ])
      setStats(statsRes.data)
      setMovers(researchRes.data?.biggest_movers || [])
      setInstruments(researchRes.data?.instruments?.slice(0, 4) || [])
      setOpenTrades(openRes.data?.trades || [])
      setNews(newsRes.data?.news || [])
    } catch (e: any) {
      setError(e?.message || 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  const isPositive = (val: number) => val >= 0

  const filteredNews = newsFilter === 'All'
    ? news
    : newsFilter === 'High impact'
      ? news.filter(n => n.impact === 'high')
      : news.filter(n => n.symbols.includes(newsFilter))

  // Filter chips: All, High impact, then each symbol that appears in the feed.
  const newsSymbols = Array.from(new Set(news.flatMap(n => n.symbols))).sort()
  const newsCategories = ['All', 'High impact', ...newsSymbols]

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Loading trading data...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Overview of your trading activity and market news</p>
        </div>
        {stats?.source === 'mt5' ? (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live · MT5 terminal
          </span>
        ) : stats?.source === 'journal' ? (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400" title="MT5 bridge unreachable — showing the durable journal of your last closed trades">
            Journal · MT5 offline
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

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
            <DollarSign className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(stats?.total_pnl || 0) ? 'text-green-400' : 'text-red-400'}`}>
              ${(stats?.total_pnl || 0).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.closed_trades || 0} closed + {stats?.open_trades || 0} open
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
            <TrendingUp className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(stats?.win_rate || 0).toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              {stats?.winning_trades || 0} wins / {stats?.losing_trades || 0} losses
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Trades</CardTitle>
            <Activity className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mt5.connected ? mt5.positions.length : (stats?.open_trades || 0)}</div>
            <p className="text-xs text-muted-foreground">
              {mt5.connected
                ? <>MT5 open · <span className={mt5.totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}>{mt5.totalProfit >= 0 ? '+' : ''}${mt5.totalProfit.toFixed(2)}</span></>
                : `${openTrades.length} open positions`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg R</CardTitle>
            <Target className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {stats?.r_tracked_trades && stats.r_tracked_trades > 0 ? (
              <>
                <div className={`text-2xl font-bold ${isPositive(stats?.avg_r || 0) ? 'text-green-400' : 'text-red-400'}`}>
                  {(stats?.avg_r || 0).toFixed(2)}R
                </div>
                <p className="text-xs text-muted-foreground">
                  Total {(stats?.total_r || 0).toFixed(2)}R · from {stats.r_tracked_trades} tracked trade{stats.r_tracked_trades === 1 ? '' : 's'}
                </p>
              </>
            ) : (
              <>
                <div className="text-2xl font-bold text-muted-foreground">—</div>
                <p className="text-xs text-muted-foreground">
                  R is measured on trades placed/seen with a stop-loss. New trades will populate it.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Real-time market news, tagged with the instruments each item can move */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Newspaper className="w-4 h-4" />
            Market News
            <span className="text-xs font-normal text-muted-foreground">— live, tagged by affected pair</span>
          </CardTitle>
          <div className="flex items-center gap-1 flex-wrap justify-end">
            {newsCategories.map((c) => (
              <button
                key={c}
                onClick={() => setNewsFilter(c)}
                className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                  newsFilter === c ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {filteredNews.length === 0 ? (
            <p className="text-muted-foreground text-sm text-center py-4">No news available</p>
          ) : (
            <div className="space-y-2.5 max-h-[440px] overflow-y-auto">
              {filteredNews.map((item, i) => (
                <div key={i} className="p-3 rounded-lg border border-border bg-card hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                      item.impact === 'high' ? 'bg-red-500/15 text-red-400' : item.impact === 'medium' ? 'bg-amber-500/15 text-amber-400' : 'bg-muted text-muted-foreground'
                    }`}>
                      {item.impact} impact
                    </span>
                    <span className="text-xs text-muted-foreground">{item.source}</span>
                    {item.timestamp && (
                      <span className="text-xs text-muted-foreground" title={new Date(item.timestamp).toLocaleString()}>
                        {relativeTime(item.timestamp)} · {new Date(item.timestamp).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  {item.link ? (
                    <a href={item.link} target="_blank" rel="noreferrer" className="text-sm font-semibold leading-tight hover:text-primary">
                      {item.title}
                    </a>
                  ) : (
                    <h3 className="text-sm font-semibold leading-tight">{item.title}</h3>
                  )}
                  {item.summary && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.summary}</p>}
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    {item.symbols.map((s) => (
                      <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
                        {s}
                      </span>
                    ))}
                    {item.reason && <span className="text-[11px] text-muted-foreground italic">{item.reason}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Streaks & Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Performance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Expectancy</span>
              <span className={`font-semibold ${isPositive(stats?.avg_pnl || 0) ? 'text-green-400' : 'text-red-400'}`}>
                ${(stats?.avg_pnl || 0).toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Best Trade</span>
              <span className="font-semibold text-green-400">${(stats?.best_trade || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Worst Trade</span>
              <span className="font-semibold text-red-400">${(stats?.worst_trade || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Max Drawdown</span>
              <span className="font-semibold text-red-400">{(stats?.max_drawdown || 0).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Max Win Streak</span>
              <span className="font-semibold text-green-400">{stats?.max_win_streak || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Max Loss Streak</span>
              <span className="font-semibold text-red-400">{stats?.max_loss_streak || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Current Streak</span>
              <span className={`font-semibold ${isPositive(stats?.current_streak || 0) ? 'text-green-400' : 'text-red-400'}`}>
                {stats?.current_streak || 0}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Market Movers */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Market Movers
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {movers.length === 0 ? (
              <p className="text-muted-foreground text-sm">No market data available</p>
            ) : (
              movers.map((m) => (
                <div key={m.symbol} className="flex items-center justify-between p-2 rounded bg-muted">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">{m.symbol}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      m.trend === 'BULLISH' ? 'bg-green-100 text-green-800' : m.trend === 'BEARISH' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {m.trend}
                    </span>
                  </div>
                  <div className={`text-sm font-semibold ${isPositive(m.change_pct) ? 'text-green-400' : 'text-red-400'}`}>
                    {isPositive(m.change_pct) ? '+' : ''}{m.change_pct.toFixed(2)}%
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Open Positions — live MT5 when connected (managed here or on MT5 Terminal / What's Up) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              Open Positions
              {mt5.connected && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">MT5 live</span>}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {mt5.connected || mt5.positions.length > 0 ? (
              <Mt5PositionsPanel variant="compact" limit={5} />
            ) : openTrades.length === 0 ? (
              <p className="text-muted-foreground text-sm">No open positions</p>
            ) : (
              openTrades.slice(0, 5).map((t) => {
                const totalPnl = (t.realized_pnl || 0) + (t.unrealized_pnl || 0)
                return (
                  <div key={t.id} className="flex items-center justify-between p-2 rounded bg-muted">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                        t.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {t.side}
                      </span>
                      <span className="font-semibold text-sm">{t.symbol}</span>
                      <span className="text-xs text-muted-foreground">{t.strategy}</span>
                    </div>
                    <div className={`text-sm font-semibold ${isPositive(totalPnl) ? 'text-green-400' : 'text-red-400'}`}>
                      ${totalPnl.toFixed(2)}
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Instruments Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Instruments</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {instruments.map((inst) => (
              <div key={inst.symbol} className="p-3 rounded-lg border border-border bg-card">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm">{inst.symbol}</span>
                  <span className={`text-xs ${isPositive(inst.change_pct) ? 'text-green-400' : 'text-red-400'}`}>
                    {isPositive(inst.change_pct) ? '+' : ''}{inst.change_pct.toFixed(2)}%
                  </span>
                </div>
                <div className="text-lg font-bold font-mono">{inst.current_price?.toFixed(2) || '-'}</div>
                <div className="text-xs text-muted-foreground mt-1">{inst.label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
