import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  Target, Shield, AlertTriangle, Zap, CheckCircle, RefreshCw, BarChart3, Sparkles
} from 'lucide-react'
import { tradesApi, ordersApi, playgroundApi } from '@/api/client'

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
  created_at: string
  current_price?: number
}

interface LotCalc {
  symbol: string
  label: string
  kind: string
  entry_price: number
  stop_loss: number
  price_distance: number
  pip_distance: number
  risk_amount: number
  risk_pct: number
  lot_size: number
  unit: string
  contract_size: number
  leverage: number
  notional_value: number
  margin_required: number
  actual_risk: number
  actual_risk_pct: number
  tick_size: number
  tick_value: number
  digits: number
  account_balance?: number
  error?: string
}

const INSTRUMENTS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!']

// Standard 1R distances per instrument (in price terms)
const R_DISTANCES: Record<string, number> = {
  'EURUSD': 0.0020,
  'GBPUSD': 0.0020,
  'USDJPY': 0.20,
  'NQ1!': 15.0,
  'ES1!': 10.0,
  'XAUUSD': 3.0,
  'BTCUSD': 0.02,  // 2% — will multiply by price
  'CL1!': 1.0,
}

function getRDistance(symbol: string, price: number): number {
  const base = R_DISTANCES[symbol] || 0.01
  if (symbol === 'BTCUSD') {
    return price * base
  }
  return base
}

export default function Execute() {
  const [symbol, setSymbol] = useState('EURUSD')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [entryPrice, setEntryPrice] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [tp1, setTp1] = useState('')
  const [tp2, setTp2] = useState('')
  const [tp3, setTp3] = useState('')
  const [accountBalance, setAccountBalance] = useState('10000')
  const [riskPct, setRiskPct] = useState('1')
  const [strategy, setStrategy] = useState('')
  const [notes, setNotes] = useState('')
  const [lotCalc, setLotCalc] = useState<LotCalc | null>(null)
  const [lotLoading, setLotLoading] = useState(false)
  const [orderLoading, setOrderLoading] = useState(false)
  const [trades, setTrades] = useState<Trade[]>([])
  const [stats, setStats] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [livePrice, setLivePrice] = useState<number | null>(null)
  const [priceLoading, setPriceLoading] = useState(false)

  const fetchOpenTrades = useCallback(async () => {
    try {
      const res = await tradesApi.open()
      setTrades(res.data?.trades || [])
      const statsRes = await tradesApi.stats()
      setStats(statsRes.data)
    } catch (e) {
      console.error('Failed to fetch trades', e)
    }
  }, [])

  useEffect(() => {
    fetchOpenTrades()
    const interval = setInterval(fetchOpenTrades, 15000)
    return () => clearInterval(interval)
  }, [fetchOpenTrades])

  // Auto-fill SL/TP when side changes
  useEffect(() => {
    const ep = parseFloat(entryPrice)
    if (ep > 0) {
      autoFillSLTP(ep)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [side])

  // Auto-fetch live price when symbol changes
  useEffect(() => {
    async function fetchPrice() {
      setPriceLoading(true)
      try {
        const res = await playgroundApi.getPrice(symbol)
        const p = res.data?.price
        if (p) {
          setLivePrice(p)
          setEntryPrice(p.toString())
          // Auto-calculate SL/TP after setting entry
          autoFillSLTP(p)
        }
      } catch (e) {
        console.error('Price fetch failed', e)
      } finally {
        setPriceLoading(false)
      }
    }
    fetchPrice()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol])

  function autoFillSLTP(price: number) {
    const rDist = getRDistance(symbol, price)
    const digits = symbol === 'BTCUSD' ? 0 : symbol === 'USDJPY' ? 3 : symbol === 'EURUSD' || symbol === 'GBPUSD' ? 5 : 2

    if (side === 'BUY') {
      setStopLoss((price - rDist).toFixed(digits))
      setTp1((price + rDist).toFixed(digits))
      setTp2((price + 2 * rDist).toFixed(digits))
      setTp3((price + 3 * rDist).toFixed(digits))
    } else {
      setStopLoss((price + rDist).toFixed(digits))
      setTp1((price - rDist).toFixed(digits))
      setTp2((price - 2 * rDist).toFixed(digits))
      setTp3((price - 3 * rDist).toFixed(digits))
    }
  }

  const handleAutoFill = () => {
    const ep = parseFloat(entryPrice)
    if (!ep || ep <= 0) {
      setError('Entry price required for auto-fill')
      return
    }
    autoFillSLTP(ep)
  }

  const calculateLot = async () => {
    setLotLoading(true)
    setError(null)
    try {
      const ep = parseFloat(entryPrice) || undefined
      const sl = parseFloat(stopLoss)
      const ab = parseFloat(accountBalance)
      const rp = parseFloat(riskPct)

      if (!sl || sl <= 0) {
        setError('Stop loss is required for lot calculation')
        setLotLoading(false)
        return
      }

      const res = await ordersApi.calculateLot({
        symbol,
        entry_price: ep,
        stop_loss: sl,
        account_balance: ab,
        risk_pct: rp,
      })
      setLotCalc(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Lot calculation failed')
    } finally {
      setLotLoading(false)
    }
  }

  // Auto-calculate lot when SL/TP change (after auto-fill)
  useEffect(() => {
    if (entryPrice && stopLoss && !lotCalc) {
      const timer = setTimeout(() => calculateLot(), 500)
      return () => clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryPrice, stopLoss])

  const placeOrder = async () => {
    setOrderLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const sl = parseFloat(stopLoss)
      if (!sl || sl <= 0) {
        setError('Stop loss is required')
        setOrderLoading(false)
        return
      }

      const res = await ordersApi.create({
        symbol,
        side,
        entry_price: entryPrice ? parseFloat(entryPrice) : undefined,
        stop_loss: sl,
        take_profit_1: tp1 ? parseFloat(tp1) : undefined,
        take_profit_2: tp2 ? parseFloat(tp2) : undefined,
        take_profit_3: tp3 ? parseFloat(tp3) : undefined,
        account_balance: parseFloat(accountBalance),
        risk_pct: parseFloat(riskPct),
        strategy: strategy || undefined,
        notes: notes || undefined,
      })
      setSuccess(`Trade created: ${res.data.symbol} ${res.data.side} @ ${res.data.quantity} lots`)
      fetchOpenTrades()
      setLotCalc(null)
      // Reset form
      setTp1('')
      setTp2('')
      setTp3('')
      setStopLoss('')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Order placement failed')
    } finally {
      setOrderLoading(false)
    }
  }

  const partialClose = async (tradeId: string, fraction: number) => {
    try {
      const exitPrice = prompt('Enter exit price for partial close:')
      if (!exitPrice) return
      await tradesApi.partialClose(tradeId, fraction, parseFloat(exitPrice), 'TP')
      fetchOpenTrades()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Partial close failed')
    }
  }

  const fullClose = async (tradeId: string) => {
    try {
      const exitPrice = prompt('Enter exit price for full close:')
      if (!exitPrice) return
      await tradesApi.fullClose(tradeId, parseFloat(exitPrice))
      fetchOpenTrades()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Close failed')
    }
  }

  const isPositive = (val: number) => val >= 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Execution Console</h1>
        <p className="text-muted-foreground">Place orders with automatic lot calculation and 1R-based targets</p>
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

      <div className="grid gap-4 md:grid-cols-2">
        {/* Order Entry Form */}
        <Card>
          <CardHeader>
            <CardTitle>Order Entry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Symbol</label>
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  {INSTRUMENTS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Direction</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSide('BUY')}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${
                      side === 'BUY' ? 'bg-green-600 text-white' : 'border bg-background'
                    }`}
                  >
                    Long
                  </button>
                  <button
                    onClick={() => setSide('SELL')}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${
                      side === 'SELL' ? 'bg-red-600 text-white' : 'border bg-background'
                    }`}
                  >
                    Short
                  </button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Entry Price</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.00001"
                    value={entryPrice}
                    onChange={(e) => setEntryPrice(e.target.value)}
                    className="w-full px-3 py-2 pr-8 border rounded-md bg-background"
                  />
                  {priceLoading && (
                    <RefreshCw className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-muted-foreground" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {livePrice ? `Live: ${livePrice}` : 'Auto-fetched from market'}
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-red-500">Stop Loss *</label>
                <input
                  type="number"
                  step="0.00001"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-green-500">Take Profit 1</label>
                <input
                  type="number"
                  step="0.00001"
                  value={tp1}
                  onChange={(e) => setTp1(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-green-500">Take Profit 2</label>
                <input
                  type="number"
                  step="0.00001"
                  value={tp2}
                  onChange={(e) => setTp2(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-green-500">Take Profit 3</label>
                <input
                  type="number"
                  step="0.00001"
                  value={tp3}
                  onChange={(e) => setTp3(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Strategy</label>
                <input
                  type="text"
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                  placeholder="FVG, OB, etc."
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Account Balance ($)</label>
                <input
                  type="number"
                  value={accountBalance}
                  onChange={(e) => setAccountBalance(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Risk %</label>
                <input
                  type="number"
                  step="0.1"
                  value={riskPct}
                  onChange={(e) => setRiskPct(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Trade setup notes..."
                className="w-full px-3 py-2 border rounded-md bg-background min-h-[60px]"
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handleAutoFill}
                variant="outline"
                className="flex-1"
                disabled={!entryPrice}
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Auto Set SL/TP (1R)
              </Button>
              <Button
                onClick={calculateLot}
                disabled={lotLoading}
                variant="outline"
                className="flex-1"
              >
                <BarChart3 className="w-4 h-4 mr-2" />
                {lotLoading ? 'Calculating...' : 'Calculate Lot'}
              </Button>
              <Button
                onClick={placeOrder}
                disabled={orderLoading}
                className="flex-1"
              >
                <Zap className="w-4 h-4 mr-2" />
                {orderLoading ? 'Placing...' : 'Place Order'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Lot Calculation Result */}
        <Card>
          <CardHeader>
            <CardTitle>Lot Calculator</CardTitle>
          </CardHeader>
          <CardContent>
            {lotCalc ? (
              lotCalc.error ? (
                <div className="text-red-400 text-sm">{lotCalc.error}</div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-muted-foreground">Lot Size</div>
                      <div className="text-xl font-bold">{lotCalc.lot_size.toFixed(4)}</div>
                      <div className="text-xs text-muted-foreground">{lotCalc.unit}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-muted-foreground">Leverage</div>
                      <div className="text-xl font-bold">1:{lotCalc.leverage}</div>
                      <div className="text-xs text-muted-foreground">{lotCalc.label}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-muted-foreground">Risk Amount</div>
                      <div className="text-lg font-semibold">${lotCalc.risk_amount.toFixed(2)}</div>
                      <div className="text-xs text-muted-foreground">{lotCalc.risk_pct}% of ${lotCalc.account_balance || 10000}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-muted-foreground">Margin Required</div>
                      <div className="text-lg font-semibold">${lotCalc.margin_required.toFixed(2)}</div>
                      <div className="text-xs text-muted-foreground">Notional: ${lotCalc.notional_value.toFixed(0)}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                    <div>Price Dist: {lotCalc.price_distance.toFixed(lotCalc.digits)}</div>
                    <div>Pip Dist: {lotCalc.pip_distance.toFixed(2)}</div>
                    <div>Actual Risk: {lotCalc.actual_risk_pct}%</div>
                  </div>

                  <div className="p-2 rounded bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-400">
                    <Shield className="w-3 h-3 inline mr-1" />
                    Tick size: {lotCalc.tick_size}, Tick value: ${lotCalc.tick_value}
                  </div>
                </div>
              )
            ) : (
              <div className="text-center text-muted-foreground py-8">
                <BarChart3 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Select instrument and click Calculate to see lot size</p>
                <p className="text-xs mt-1">Leverage: Forex 1:100, Gold 1:200, Indices 1:100, Crypto 1:30</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Open Trades */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Open Trades</CardTitle>
          <div className="text-sm text-muted-foreground">
            {stats?.open_trades || 0} open | {stats?.total_trades || 0} total
          </div>
        </CardHeader>
        <CardContent>
          {trades.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No open trades. Place an order above to start tracking.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {trades.map((trade) => (
                <div key={trade.id} className="p-4 rounded-lg border border-border bg-card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        trade.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {trade.side}
                      </span>
                      <span className="font-bold text-lg">{trade.symbol}</span>
                      <span className="text-sm text-muted-foreground">{trade.strategy}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-bold ${
                        isPositive((trade.realized_pnl || 0) + (trade.unrealized_pnl || 0)) ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${((trade.realized_pnl || 0) + (trade.unrealized_pnl || 0)).toFixed(2)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        R: {trade.total_r?.toFixed(2) || '0'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-3">
                    <div className="p-2 rounded bg-muted">
                      <div className="text-muted-foreground">Entry</div>
                      <div className="font-mono font-semibold">{trade.entry_price}</div>
                    </div>
                    <div className="p-2 rounded bg-muted">
                      <div className="text-muted-foreground">Current</div>
                      <div className="font-mono font-semibold">{trade.current_price || '-'}</div>
                    </div>
                    <div className="p-2 rounded bg-muted">
                      <div className="text-muted-foreground">SL</div>
                      <div className="font-mono font-semibold text-red-400">{trade.stop_loss}</div>
                    </div>
                    <div className="p-2 rounded bg-muted">
                      <div className="text-muted-foreground">Quantity</div>
                      <div className="font-mono font-semibold">{trade.remaining_quantity?.toFixed(4)} / {trade.initial_quantity?.toFixed(4)}</div>
                    </div>
                  </div>

                  {trade.legs && trade.legs.length > 0 && (
                    <div className="mb-3">
                      <div className="text-xs text-muted-foreground mb-1">Closed Legs</div>
                      <div className="flex gap-2 flex-wrap">
                        {trade.legs.map((leg, i) => (
                          <span key={i} className={`text-xs px-2 py-1 rounded ${
                            isPositive(leg.pnl) ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {leg.label}: ${leg.pnl.toFixed(2)} ({leg.r_multiple?.toFixed(2)}R)
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => partialClose(trade.id, 0.3)}
                      className="px-3 py-1.5 text-xs rounded bg-yellow-100 text-yellow-800 hover:bg-yellow-200"
                    >
                      Close 30%
                    </button>
                    <button
                      onClick={() => partialClose(trade.id, 0.5)}
                      className="px-3 py-1.5 text-xs rounded bg-yellow-100 text-yellow-800 hover:bg-yellow-200"
                    >
                      Close 50%
                    </button>
                    <button
                      onClick={() => fullClose(trade.id)}
                      className="px-3 py-1.5 text-xs rounded bg-red-100 text-red-800 hover:bg-red-200"
                    >
                      Close All
                    </button>
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
