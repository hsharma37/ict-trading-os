import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { tradesApi, researchApi, marketApi } from '@/api/client'
import { useMt5 } from '@/hooks/useMt5'
import Mt5PositionsPanel from '@/components/Mt5PositionsPanel'
import Mt5PositionDetail from '@/components/Mt5PositionDetail'
import {
  Eye, Target, Shield, AlertTriangle, Crosshair, DollarSign,
  Clock, Zap, Percent, MoveRight, RefreshCw, TrendingUp, TrendingDown, 
  Minus, ArrowUp, ArrowDown, Type
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
  current_price?: number
  legs: any[]
  strategy?: string
  created_at: string
  account_balance: number
  risk_pct: number
  risk_amount: number
  sl_at_be?: boolean
  tp1_hit?: boolean
  tp2_hit?: boolean
  tp3_hit?: boolean
}

interface Instrument {
  symbol: string
  label: string
  current_price: number
  change_pct: number
  trend: string
  sentiment: string
  support: number | null
  resistance: number | null
}

interface PriceData {
  symbol: string
  price: number
  bid: number
  ask: number
  change: number
  change_pct: number
  source: string
  timestamp: string
}

function getKillzoneInfo() {
  const now = new Date()
  const utcHour = now.getUTCHours()
  const utcMinute = now.getUTCMinutes()
  const timeVal = utcHour + utcMinute / 60

  const zones = [
    { name: 'London Open', start: 7, end: 10, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
    { name: 'NY AM', start: 12, end: 15, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    { name: 'NY PM', start: 17, end: 21, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
    { name: 'Asian', start: 21, end: 8, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  ]

  for (const z of zones) {
    const inZone = z.start < z.end
      ? (timeVal >= z.start && timeVal < z.end)
      : (timeVal >= z.start || timeVal < z.end)
    if (inZone) return { active: z.name, color: z.color, bg: z.bg, border: z.border, time: `${String(utcHour).padStart(2,'0')}:${String(utcMinute).padStart(2,'0')} UTC` }
  }
  return { active: 'London Close', color: 'text-muted-foreground', bg: 'bg-muted', border: 'border-border', time: `${String(utcHour).padStart(2,'0')}:${String(utcMinute).padStart(2,'0')} UTC` }
}

function getPipSize(symbol: string): number {
  if (symbol === 'XAUUSD' || symbol === 'CL1!') return 0.01
  if (symbol === 'USDJPY') return 0.01
  return 0.0001
}

function calcPipDistance(price1: number, price2: number, symbol: string): number {
  const pipSize = getPipSize(symbol)
  return Math.round(Math.abs(price1 - price2) / pipSize)
}

export default function WhatsUp() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [livePrices, setLivePrices] = useState<Record<string, PriceData>>({})
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [closing, setClosing] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [manualPrice, setManualPrice] = useState('')
  const [manualSymbol, setManualSymbol] = useState('')
  const [countdown, setCountdown] = useState(10)

  const selectedTradeRef = useRef<Trade | null>(null)
  // Keep ref in sync with state
  useEffect(() => { selectedTradeRef.current = selectedTrade }, [selectedTrade])

  const fetchData = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true)
    try {
      setError(null)
      const [tradesRes, researchRes] = await Promise.all([
        tradesApi.open(),
        researchApi.all(),
      ])
      const openTrades: Trade[] = tradesRes.data?.trades || []
      setTrades(openTrades)
      setInstruments(researchRes.data?.instruments || [])
      
      // Fetch live prices for all trade symbols
      const symbols = Array.from(new Set(openTrades.map((t: Trade) => t.symbol))) as string[]
      if (symbols.length > 0) {
        const pricePromises = symbols.map(async (sym: string) => {
          try {
            const res = await marketApi.getPrice(sym)
            return { sym, data: res.data }
          } catch (e) {
            return { sym, data: null }
          }
        })
        const priceResults = await Promise.all(pricePromises)
        const priceMap: Record<string, PriceData> = {}
        priceResults.forEach((r: any) => {
          if (r.data) priceMap[r.sym] = r.data
        })
        setLivePrices(priceMap)
      }
      
      const currentSelected = selectedTradeRef.current
      if (currentSelected && openTrades.length > 0) {
        const updated = openTrades.find((t: Trade) => t.id === currentSelected.id)
        if (updated) setSelectedTrade(updated)
      }
      setLastUpdate(new Date())
      setCountdown(10)
    } catch (e: any) {
      setError(e?.message || 'Failed to load data')
    } finally {
      setLoading(false)
      if (showRefresh) setRefreshing(false)
    }
  }, []) // No dependencies — stable reference

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => {
      fetchData()
    }, 10000)
    return () => clearInterval(interval)
  }, [fetchData]) // Interval runs once because fetchData is stable.

  // Countdown timer — independent of lastUpdate to avoid re-subscription
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 10))
    }, 1000)
    return () => clearInterval(timer)
  }, []) // Empty deps — countdown runs independently

  const isPositive = (val: number) => val >= 0
  const totalPnl = trades.reduce((sum, t) => sum + (t.realized_pnl || 0) + (t.unrealized_pnl || 0), 0)
  const totalRisk = trades.reduce((sum, t) => sum + (t.risk_amount || 0), 0)

  const selectedInstrument = instruments.find(i => i.symbol === selectedTrade?.symbol)
  const killzone = getKillzoneInfo()
  const mt5 = useMt5()
  const [selectedMt5Ticket, setSelectedMt5Ticket] = useState<string | null>(null)
  // Default the detail view to the first position; keep selection valid as positions change.
  const selectedMt5 = mt5.positions.find(p => p.ticket === selectedMt5Ticket) || mt5.positions[0] || null

  const handlePartialClose = async (trade: Trade, fraction: number, label: string) => {
    const price = livePrices[trade.symbol]?.price || trade.current_price
    if (!price) return
    setClosing(trade.id)
    try {
      await tradesApi.partialClose(trade.id, fraction, price, label)
      setSuccessMsg(`${trade.symbol} ${label}: ${Math.round(fraction * 100)}% closed at ${price}`)
      setTimeout(() => setSuccessMsg(null), 4000)
      await fetchData(true)
    } catch (e: any) {
      setError(e?.message || 'Close failed')
      setTimeout(() => setError(null), 4000)
    } finally {
      setClosing(null)
    }
  }

  const handleFullClose = async (trade: Trade) => {
    const price = livePrices[trade.symbol]?.price || trade.current_price
    if (!price) return
    setClosing(trade.id)
    try {
      await tradesApi.fullClose(trade.id, price)
      setSuccessMsg(`${trade.symbol} position fully closed at ${price}`)
      setTimeout(() => setSuccessMsg(null), 4000)
      setSelectedTrade(null)
      await fetchData(true)
    } catch (e: any) {
      setError(e?.message || 'Close failed')
      setTimeout(() => setError(null), 4000)
    } finally {
      setClosing(null)
    }
  }

  const handleMoveSlToBe = async (trade: Trade) => {
    try {
      await tradesApi.moveSlToBe(trade.id)
      setSuccessMsg(`${trade.symbol} SL moved to breakeven (${trade.entry_price})`)
      setTimeout(() => setSuccessMsg(null), 4000)
      await fetchData(true)
    } catch (e: any) {
      setError(e?.message || 'Move SL failed')
      setTimeout(() => setError(null), 4000)
    }
  }

  const handleSetManualPrice = async () => {
    if (!manualSymbol || !manualPrice) return
    try {
      const price = parseFloat(manualPrice)
      await marketApi.setManualPrice(manualSymbol, price)
      setSuccessMsg(`Manual price set for ${manualSymbol}: ${price}`)
      setTimeout(() => setSuccessMsg(null), 4000)
      setManualPrice('')
      await fetchData(true)
    } catch (e: any) {
      setError(e?.message || 'Failed to set manual price')
      setTimeout(() => setError(null), 4000)
    }
  }

  const priceProgress = (trade: Trade) => {
    const entry = trade.entry_price
    const current = livePrices[trade.symbol]?.price || trade.current_price || entry
    const sl = trade.stop_loss || entry
    const tp3 = trade.take_profit_3 || trade.take_profit_1 || entry
    if (!entry || !sl || !tp3) return null

    const range = Math.abs(tp3 - sl)
    if (range === 0) return null

    const progress = (current - sl) / range
    const pct = Math.max(0, Math.min(100, progress * 100))

    const tp1Pct = trade.take_profit_1 ? ((trade.take_profit_1 - sl) / range) * 100 : 33
    const tp2Pct = trade.take_profit_2 ? ((trade.take_profit_2 - sl) / range) * 100 : 66
    const tp3Pct = trade.take_profit_3 ? ((trade.take_profit_3 - sl) / range) * 100 : 100
    const entryPct = ((entry - sl) / range) * 100

    return { pct, tp1Pct, tp2Pct, tp3Pct, entryPct }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">What's Up?</h1>
        <p className="text-muted-foreground">Loading live trade data...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">What's Up?</h1>
          <p className="text-muted-foreground">Live trade visualization and market status</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Next update: {countdown}s</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => fetchData(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-center gap-2">
          <Zap className="w-4 h-4" />
          {successMsg}
        </div>
      )}

      {/* Manual Price Override */}
      <Card className="border-dashed border-primary/30">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
            <Type className="w-4 h-4" />
            <span>Manual Price Override (from MT5/broker)</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="px-2 py-1.5 border rounded-md bg-background text-sm"
              value={manualSymbol}
              onChange={(e) => setManualSymbol(e.target.value)}
            >
              <option value="">Select symbol</option>
              {['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'NQ1!', 'ES1!', 'CL1!', 'BTCUSD'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <Input
              type="number"
              step="0.01"
              placeholder="Price"
              className="w-32 text-sm"
              value={manualPrice}
              onChange={(e) => setManualPrice(e.target.value)}
            />
            <Button size="sm" variant="outline" onClick={handleSetManualPrice} disabled={!manualSymbol || !manualPrice}>
              Set Price
            </Button>
            <Button size="sm" variant="ghost" onClick={async () => {
              if (!manualSymbol) return
              await marketApi.clearManualPrice(manualSymbol)
              setSuccessMsg(`Cleared manual price for ${manualSymbol}`)
              setTimeout(() => setSuccessMsg(null), 3000)
              await fetchData(true)
            }} disabled={!manualSymbol}>
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Killzone / Session Card */}
      <Card className={`${killzone.bg} border ${killzone.border}`}>
        <CardContent className="py-3 px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className={`w-5 h-5 ${killzone.color}`} />
              <div>
                <div className={`text-sm font-bold ${killzone.color}`}>
                  {killzone.active} Session Active
                </div>
                <div className="text-xs text-muted-foreground">{killzone.time}</div>
              </div>
            </div>
            <div className="text-xs text-muted-foreground">
              London: 07-10 | NY AM: 12-15 | NY PM: 17-21 | Asian: 21-08 UTC
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Eye className="w-4 h-4" /> Open Trades
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{trades.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <DollarSign className="w-4 h-4" /> Total P&L
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(totalPnl) ? 'text-green-400' : 'text-red-400'}`}>
              ${totalPnl.toFixed(2)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="w-4 h-4" /> Total Risk
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${totalRisk.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground">{trades.length > 0 ? (totalRisk / (trades[0]?.account_balance || 10000) * 100).toFixed(1) : 0}% of account</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="w-4 h-4" /> Total R
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive(trades.reduce((s, t) => s + (t.total_r || 0), 0)) ? 'text-green-400' : 'text-red-400'}`}>
              {trades.reduce((s, t) => s + (t.total_r || 0), 0).toFixed(2)}R
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Live MT5 Positions — broker-side positions with SL/TP progress + management */}
      {(mt5.connected || mt5.positions.length > 0) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Crosshair className="w-5 h-5 text-primary" />
              Live MT5 Positions
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">broker feed</span>
              <span className="text-xs text-muted-foreground font-normal ml-auto">
                {mt5.positions.length} open · <span className={mt5.totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}>{mt5.totalProfit >= 0 ? '+' : ''}${mt5.totalProfit.toFixed(2)}</span>
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {mt5.positions.length === 0 ? (
              <Mt5PositionsPanel variant="visual" />
            ) : (
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-3">
                  <Mt5PositionsPanel
                    variant="visual"
                    onSelect={setSelectedMt5Ticket}
                    selectedTicket={selectedMt5?.ticket}
                  />
                </div>
                <div className="md:col-span-2">
                  {selectedMt5 && <Mt5PositionDetail position={selectedMt5} />}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {trades.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Crosshair className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-semibold mb-2">No Internal Trades</h3>
            <p className="text-sm max-w-md mx-auto mb-4">
              Go to the Execute page to place a trade. Once you have open positions, 
              this dashboard will show real-time P&L, R-multiples, and trade lifecycle tracking.
            </p>
            <div className="text-xs text-muted-foreground">
              Live updates every 10 seconds
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          {/* Trade List */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">Open Positions</h2>
            {trades.map((trade) => {
              const totalPnl = (trade.realized_pnl || 0) + (trade.unrealized_pnl || 0)
              const isSelected = selectedTrade?.id === trade.id
              const livePrice = livePrices[trade.symbol]
              const priceChange = livePrice ? livePrice.price - trade.entry_price : 0
              const priceDirection = priceChange > 0 ? 'up' : priceChange < 0 ? 'down' : 'flat'
              
              return (
                <button
                  key={trade.id}
                  onClick={() => setSelectedTrade(trade)}
                  className={`w-full p-4 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                      : 'border-border bg-card hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                        trade.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {trade.side}
                      </span>
                      <span className="font-bold">{trade.symbol}</span>
                      {trade.sl_at_be && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">BE</span>
                      )}
                      {trade.tp1_hit && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-800 font-medium">TP1</span>
                      )}
                    </div>
                    <div className={`text-sm font-bold ${isPositive(totalPnl) ? 'text-green-400' : 'text-red-400'}`}>
                      ${totalPnl.toFixed(2)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Entry: {trade.entry_price}</span>
                    <span className="flex items-center gap-0.5">
                      {priceDirection === 'up' && <ArrowUp className="w-3 h-3 text-green-400" />}
                      {priceDirection === 'down' && <ArrowDown className="w-3 h-3 text-red-400" />}
                      {priceDirection === 'flat' && <Minus className="w-3 h-3" />}
                      {livePrice ? livePrice.price.toFixed(2) : '-'}
                    </span>
                    <span className="text-[10px] opacity-60">
                      {livePrice?.source === 'manual' ? '(manual)' : livePrice?.source === 'yahoo' ? '(Yahoo)' : '(auto)'}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Qty: {trade.remaining_quantity?.toFixed(3)} / {trade.initial_quantity?.toFixed(3)} | R: {trade.total_r?.toFixed(2) || '0'}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Trade Detail Visualization */}
          {selectedTrade && (() => {
            const livePrice = livePrices[selectedTrade.symbol]
            const currentPrice = livePrice?.price || selectedTrade.current_price || selectedTrade.entry_price
            const priceChange = currentPrice - selectedTrade.entry_price
            const priceDirection = priceChange > 0 ? 'up' : priceChange < 0 ? 'down' : 'flat'
            const isBuy = selectedTrade.side === 'BUY'
            const slPips = selectedTrade.stop_loss ? calcPipDistance(currentPrice, selectedTrade.stop_loss, selectedTrade.symbol) : 0
            const tp1Pips = selectedTrade.take_profit_1 ? calcPipDistance(currentPrice, selectedTrade.take_profit_1, selectedTrade.symbol) : 0
            const tp2Pips = selectedTrade.take_profit_2 ? calcPipDistance(currentPrice, selectedTrade.take_profit_2, selectedTrade.symbol) : 0
            const tp3Pips = selectedTrade.take_profit_3 ? calcPipDistance(currentPrice, selectedTrade.take_profit_3, selectedTrade.symbol) : 0
            
            return (
              <div className="md:col-span-2 space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 flex-wrap">
                      <Crosshair className="w-5 h-5" />
                      {selectedTrade.symbol} — {selectedTrade.side}
                      {selectedTrade.sl_at_be && (
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">SL at BE</span>
                      )}
                      {selectedTrade.tp1_hit && (
                        <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-800 font-medium">TP1 Hit</span>
                      )}
                      <span className="text-xs text-muted-foreground font-normal">
                        {livePrice?.source === 'manual' ? '(manual price)' : livePrice?.source === 'yahoo' ? '(Yahoo Finance)' : '(synthetic)'}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {/* Live Price Banner */}
                    <div className="flex items-center justify-between p-3 rounded-lg bg-muted mb-4">
                      <div>
                        <div className="text-xs text-muted-foreground">Live Price</div>
                        <div className="text-2xl font-bold font-mono flex items-center gap-2">
                          {currentPrice.toFixed(2)}
                          {priceDirection === 'up' && <TrendingUp className="w-5 h-5 text-green-400" />}
                          {priceDirection === 'down' && <TrendingDown className="w-5 h-5 text-red-400" />}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-muted-foreground">vs Entry</div>
                        <div className={`text-lg font-semibold ${isPositive(priceChange) ? 'text-green-400' : 'text-red-400'}`}>
                          {isPositive(priceChange) ? '+' : ''}{priceChange.toFixed(2)}
                        </div>
                      </div>
                    </div>

                    {/* Price Progress Bar */}
                    {(priceProgress(selectedTrade) !== null) && (() => {
                      const prog = priceProgress(selectedTrade)!
                      return (
                        <div className="mb-6">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">Price Progress</span>
                            <span className="text-xs text-muted-foreground">
                              {prog.pct.toFixed(1)}% toward target
                            </span>
                          </div>
                          <div className="relative h-6 bg-muted rounded-full overflow-hidden">
                            {/* SL marker */}
                            <div className="absolute left-0 top-0 h-full w-0.5 bg-red-500 z-10"></div>
                            {/* Entry marker */}
                            <div className="absolute top-0 h-full w-0.5 bg-blue-500 z-10" style={{ left: `${prog.entryPct}%` }}></div>
                            {/* TP1 marker */}
                            {selectedTrade.take_profit_1 && (
                              <div className="absolute top-0 h-full w-0.5 bg-green-400 z-10" style={{ left: `${prog.tp1Pct}%` }}></div>
                            )}
                            {/* TP2 marker */}
                            {selectedTrade.take_profit_2 && (
                              <div className="absolute top-0 h-full w-0.5 bg-green-500 z-10" style={{ left: `${prog.tp2Pct}%` }}></div>
                            )}
                            {/* TP3 marker */}
                            {selectedTrade.take_profit_3 && (
                              <div className="absolute top-0 h-full w-0.5 bg-green-600 z-10" style={{ left: `${prog.tp3Pct}%` }}></div>
                            )}
                            {/* Progress fill */}
                            <div 
                              className={`absolute left-0 top-0 h-full transition-all ${isBuy ? 'bg-green-400/50' : 'bg-red-400/50'}`}
                              style={{ width: `${prog.pct}%` }}
                            ></div>
                            {/* Current price indicator */}
                            <div 
                              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-purple-500 z-20"
                              style={{ left: `calc(${prog.pct}% - 6px)` }}
                            ></div>
                          </div>
                          <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                            <span>SL {selectedTrade.stop_loss}</span>
                            <span>Entry {selectedTrade.entry_price}</span>
                            <span>TP3 {selectedTrade.take_profit_3 || '-'}</span>
                          </div>
                        </div>
                      )
                    })()}

                    {/* Distance to Levels in Pips */}
                    <div className="grid grid-cols-4 gap-2 mb-4">
                      <div className="p-2 rounded-lg bg-red-50 border border-red-200">
                        <div className="text-[10px] text-red-600 font-medium">SL</div>
                        <div className="text-sm font-bold text-red-600">{slPips} pips</div>
                      </div>
                      <div className="p-2 rounded-lg bg-green-50 border border-green-200">
                        <div className="text-[10px] text-green-600 font-medium">TP1</div>
                        <div className="text-sm font-bold text-green-600">{tp1Pips} pips</div>
                      </div>
                      <div className="p-2 rounded-lg bg-green-50 border border-green-200">
                        <div className="text-[10px] text-green-600 font-medium">TP2</div>
                        <div className="text-sm font-bold text-green-600">{tp2Pips} pips</div>
                      </div>
                      <div className="p-2 rounded-lg bg-green-50 border border-green-200">
                        <div className="text-[10px] text-green-600 font-medium">TP3</div>
                        <div className="text-sm font-bold text-green-600">{tp3Pips} pips</div>
                      </div>
                    </div>

                    {/* Price Ladder */}
                    <div className="relative mb-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Price Ladder</span>
                        <span className="text-xs text-muted-foreground">
                          Updated: {lastUpdate.toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {/* TP3 */}
                        {selectedTrade.take_profit_3 && (
                          <div className="flex items-center gap-2">
                            <div className="w-20 text-xs text-green-400 font-medium text-right">TP3</div>
                            <div className="flex-1 h-2 rounded bg-green-200/50 relative">
                              <div className="absolute right-0 top-0 h-full w-1/3 rounded bg-green-400/30"></div>
                            </div>
                            <div className="w-24 text-xs font-mono text-right">{selectedTrade.take_profit_3.toFixed(5)}</div>
                          </div>
                        )}
                        {/* TP2 */}
                        {selectedTrade.take_profit_2 && (
                          <div className="flex items-center gap-2">
                            <div className="w-20 text-xs text-green-400 font-medium text-right">TP2</div>
                            <div className="flex-1 h-2 rounded bg-green-200/50 relative">
                              <div className="absolute right-0 top-0 h-full w-2/5 rounded bg-green-400/40"></div>
                            </div>
                            <div className="w-24 text-xs font-mono text-right">{selectedTrade.take_profit_2.toFixed(5)}</div>
                          </div>
                        )}
                        {/* TP1 */}
                        {selectedTrade.take_profit_1 && (
                          <div className="flex items-center gap-2">
                            <div className="w-20 text-xs text-green-400 font-medium text-right">TP1</div>
                            <div className="flex-1 h-2 rounded bg-green-200/50 relative">
                              <div className="absolute right-0 top-0 h-full w-1/2 rounded bg-green-400/50"></div>
                            </div>
                            <div className="w-24 text-xs font-mono text-right">{selectedTrade.take_profit_1.toFixed(5)}</div>
                          </div>
                        )}
                        {/* Entry */}
                        <div className="flex items-center gap-2">
                          <div className="w-20 text-xs text-blue-400 font-medium text-right">Entry</div>
                          <div className="flex-1 h-3 rounded bg-blue-400 relative">
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="w-3 h-3 rounded-full bg-white border-2 border-blue-500"></div>
                            </div>
                          </div>
                          <div className="w-24 text-xs font-mono font-bold text-right">{selectedTrade.entry_price.toFixed(5)}</div>
                        </div>
                        {/* Current Price */}
                        <div className="flex items-center gap-2">
                          <div className="w-20 text-xs text-purple-400 font-medium text-right">Current</div>
                          <div className="flex-1 h-3 rounded bg-purple-400/50 relative">
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="w-3 h-3 rounded-full bg-white border-2 border-purple-500 animate-pulse"></div>
                            </div>
                          </div>
                          <div className="w-24 text-xs font-mono font-bold text-right">{currentPrice.toFixed(5)}</div>
                        </div>
                        {/* SL */}
                        <div className="flex items-center gap-2">
                          <div className="w-20 text-xs text-red-400 font-medium text-right">
                            SL {selectedTrade.sl_at_be ? '(BE)' : ''}
                          </div>
                          <div className="flex-1 h-3 rounded bg-red-400 relative">
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="w-3 h-3 rounded-full bg-white border-2 border-red-500"></div>
                            </div>
                          </div>
                          <div className="w-24 text-xs font-mono font-bold text-right">{selectedTrade.stop_loss.toFixed(5)}</div>
                        </div>
                      </div>
                    </div>

                    {/* Close Action Buttons */}
                    <div className="flex flex-wrap gap-2 mb-4">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs"
                        onClick={() => handleMoveSlToBe(selectedTrade)}
                        disabled={selectedTrade.sl_at_be || selectedTrade.stop_loss === selectedTrade.entry_price}
                      >
                        <MoveRight className="w-3 h-3 mr-1" />
                        SL → BE
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs text-green-600"
                        onClick={() => handlePartialClose(selectedTrade, 0.33, 'TP1')}
                        disabled={closing === selectedTrade.id}
                      >
                        <Percent className="w-3 h-3 mr-1" />
                        Close 33%
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs text-green-600"
                        onClick={() => handlePartialClose(selectedTrade, 0.50, 'MANUAL')}
                        disabled={closing === selectedTrade.id}
                      >
                        <Percent className="w-3 h-3 mr-1" />
                        Close 50%
                      </Button>
                      <Button
                        size="sm"
                        variant="default"
                        className="text-xs"
                        onClick={() => handleFullClose(selectedTrade)}
                        disabled={closing === selectedTrade.id}
                      >
                        <DollarSign className="w-3 h-3 mr-1" />
                        Close Full
                      </Button>
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Realized</div>
                        <div className={`font-semibold ${isPositive(selectedTrade.realized_pnl) ? 'text-green-400' : 'text-red-400'}`}>
                          ${selectedTrade.realized_pnl.toFixed(2)}
                        </div>
                      </div>
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Unrealized</div>
                        <div className={`font-semibold ${isPositive(selectedTrade.unrealized_pnl) ? 'text-green-400' : 'text-red-400'}`}>
                          ${selectedTrade.unrealized_pnl.toFixed(2)}
                        </div>
                      </div>
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Total R</div>
                        <div className={`font-semibold ${isPositive(selectedTrade.total_r) ? 'text-green-400' : 'text-red-400'}`}>
                          {selectedTrade.total_r.toFixed(2)}R
                        </div>
                      </div>
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Risk</div>
                        <div className="font-semibold">${selectedTrade.risk_amount?.toFixed(2)}</div>
                      </div>
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Qty</div>
                        <div className="font-semibold">{selectedTrade.remaining_quantity?.toFixed(4)}</div>
                      </div>
                      <div className="p-3 rounded-lg bg-muted">
                        <div className="text-xs text-muted-foreground">Leverage</div>
                        <div className="font-semibold">1:{selectedTrade.symbol === 'XAUUSD' ? '10' : selectedTrade.symbol === 'CL1!' ? '20' : '100'}</div>
                      </div>
                    </div>

                    {/* Legs */}
                    {selectedTrade.legs && selectedTrade.legs.length > 0 && (
                      <div>
                        <div className="text-sm font-medium mb-2">Trade Lifecycle</div>
                        <div className="space-y-2">
                          {selectedTrade.legs.map((leg, i) => (
                            <div key={i} className="flex items-center gap-3 p-2 rounded bg-muted text-sm">
                              <div className={`w-2 h-2 rounded-full ${isPositive(leg.pnl) ? 'bg-green-400' : 'bg-red-400'}`}></div>
                              <span className="font-semibold w-16">{leg.label}</span>
                              <span className="text-muted-foreground">{Math.round(leg.fraction * 100)}% @ {leg.exit_price?.toFixed(5)}</span>
                              <div className="flex-1"></div>
                              <span className={`font-semibold ${isPositive(leg.pnl) ? 'text-green-400' : 'text-red-400'}`}>
                                ${leg.pnl.toFixed(2)} ({leg.r_multiple?.toFixed(2)}R)
                              </span>
                              <span className="text-xs text-muted-foreground">{new Date(leg.closed_at).toLocaleTimeString()}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Market Context */}
                {selectedInstrument && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Market Context</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="p-2 rounded bg-muted">
                          <div className="text-xs text-muted-foreground">Trend</div>
                          <div className={`font-semibold ${selectedInstrument.trend === 'BULLISH' ? 'text-green-400' : selectedInstrument.trend === 'BEARISH' ? 'text-red-400' : ''}`}>
                            {selectedInstrument.trend}
                          </div>
                        </div>
                        <div className="p-2 rounded bg-muted">
                          <div className="text-xs text-muted-foreground">Sentiment</div>
                          <div className="font-semibold">{selectedInstrument.sentiment}</div>
                        </div>
                        <div className="p-2 rounded bg-muted">
                          <div className="text-xs text-muted-foreground">Support</div>
                          <div className="font-semibold text-green-400">{selectedInstrument.support?.toFixed(2) || '-'}</div>
                        </div>
                        <div className="p-2 rounded bg-muted">
                          <div className="text-xs text-muted-foreground">Resistance</div>
                          <div className="font-semibold text-red-400">{selectedInstrument.resistance?.toFixed(2) || '-'}</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}
