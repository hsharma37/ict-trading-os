import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import {
  TrendingUp, DollarSign, Activity, Target, AlertTriangle, Newspaper, Globe, BarChart3
} from 'lucide-react'
import { tradesApi, researchApi, newsApi } from '@/api/client'

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
  best_trade: number
  worst_trade: number
  max_drawdown: number
  max_win_streak: number
  max_loss_streak: number
  current_streak: number
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
  headline: string
  source: string
  category: string
  symbols: string[]
  timestamp: string
  summary: string
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

  const loadData = useCallback(async () => {
    try {
      setError(null)
      
      // Fetch each endpoint independently so one failure doesn't block others
      let statsData = null
      let researchData = null
      let openData = null
      let newsData = null
      
      try {
        const res = await tradesApi.stats()
        statsData = res.data
      } catch (e: any) {
        console.error('Stats fetch failed:', e)
      }
      
      try {
        const res = await researchApi.summary()
        researchData = res.data
      } catch (e: any) {
        console.error('Research fetch failed:', e)
      }
      
      try {
        const res = await tradesApi.open()
        openData = res.data
      } catch (e: any) {
        console.error('Open trades fetch failed:', e)
      }
      
      try {
        const res = await newsApi.latest()
        newsData = res.data
      } catch (e: any) {
        console.error('News fetch failed:', e)
      }
      
      setStats(statsData)
      setMovers(researchData?.biggest_movers || [])
      setInstruments(researchData?.instruments?.slice(0, 4) || [])
      setOpenTrades(openData?.trades || [])
      setNews(newsData?.news || [])
      
      if (!statsData && !openData && !researchData) {
        setError('Unable to load dashboard data. Some services may be unavailable.')
      }
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
    : news.filter(n => n.category === newsFilter || n.symbols.includes(newsFilter))

  const newsCategories = ['All', ...Array.from(new Set(news.map(n => n.category)))]

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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Overview of your trading activity and market news</p>
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
            <div className="text-2xl font-bold">{stats?.open_trades || 0}</div>
            <p className="text-xs text-muted-foreground">
              {openTrades.length} open positions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg R</CardTitle>
            <Target className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(stats?.avg_r || 0) ? 'text-green-400' : 'text-red-400'}`}>
              {(stats?.avg_r || 0).toFixed(2)}R
            </div>
            <p className="text-xs text-muted-foreground">
              Total: {(stats?.total_r || 0).toFixed(2)}R
            </p>
          </CardContent>
        </Card>
      </div>

      {/* News Feed Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Newspaper className="w-4 h-4" />
            Market News
          </CardTitle>
          <div className="flex items-center gap-2">
            <select
              className="px-2 py-1 text-xs border rounded-md bg-background"
              value={newsFilter}
              onChange={(e) => setNewsFilter(e.target.value)}
            >
              {newsCategories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <Globe className="w-4 h-4 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          {filteredNews.length === 0 ? (
            <p className="text-muted-foreground text-sm text-center py-4">No news available</p>
          ) : (
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {filteredNews.map((item, i) => (
                <div key={i} className="p-3 rounded-lg border border-border bg-card hover:bg-muted/30 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-semibold text-primary">{item.category}</span>
                        <span className="text-xs text-muted-foreground">{item.source}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(item.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <h3 className="text-sm font-semibold leading-tight">{item.headline}</h3>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.summary}</p>
                      <div className="flex gap-1 mt-1">
                        {item.symbols.map((s) => (
                          <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
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

        {/* Open Positions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Open Positions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {openTrades.length === 0 ? (
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
