import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  Target, Shield, AlertTriangle, Zap, CheckCircle, RefreshCw, BarChart3, Sparkles, Wifi, WifiOff
} from 'lucide-react'
import { tradesApi, ordersApi, marketApi, mt5Api } from '@/api/client'
import { useMt5 } from '@/hooks/useMt5'
import Mt5PositionsPanel from '@/components/Mt5PositionsPanel'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'

type OrderType = 'market' | 'limit' | 'stop'

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
  rate_source?: string
  tick_size: number
  tick_value: number
  digits: number
  account_balance?: number
  error?: string
}

const INSTRUMENTS = SUPPORTED_SYMBOLS
const MT5_INSTRUMENTS = SUPPORTED_SYMBOLS

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
  const [orderType, setOrderType] = useState<OrderType>('market')
  const [manualLot, setManualLot] = useState('')
  // Scale-out is OPT-IN. When off, one market order with a single TP is placed.
  // When on, the lot is split into one broker position per TP (TP1/TP2/TP3).
  // Previously this fired automatically whenever TP2/TP3 were populated — and
  // since auto-fill fills all three, a single click silently opened 2-3 orders.
  const [scaleOut, setScaleOut] = useState(false)

  // Live MT5 state — when the terminal is connected, orders route to the broker.
  const mt5 = useMt5()

  // Instruments the current execution target can actually trade.
  const availableInstruments = mt5.connected ? MT5_INSTRUMENTS : INSTRUMENTS

  // Prefer the real MT5 account balance for risk sizing when connected.
  useEffect(() => {
    if (mt5.connected && mt5.account?.balance) {
      setAccountBalance(String(Math.round(mt5.account.balance)))
    }
  }, [mt5.connected, mt5.account?.balance])

  // When switching to MT5 execution, drop any symbol the broker can't trade.
  useEffect(() => {
    if (mt5.connected && !MT5_INSTRUMENTS.includes(symbol)) {
      setSymbol('EURUSD')
    }
  }, [mt5.connected, symbol])

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
        const res = await marketApi.getPrice(symbol)
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

    // Only auto-fill TP2/TP3 when the user has opted into scaling out; otherwise
    // leave them blank so a single order is placed (no surprise extra positions).
    if (side === 'BUY') {
      setStopLoss((price - rDist).toFixed(digits))
      setTp1((price + rDist).toFixed(digits))
      setTp2(scaleOut ? (price + 2 * rDist).toFixed(digits) : '')
      setTp3(scaleOut ? (price + 3 * rDist).toFixed(digits) : '')
    } else {
      setStopLoss((price + rDist).toFixed(digits))
      setTp1((price - rDist).toFixed(digits))
      setTp2(scaleOut ? (price - 2 * rDist).toFixed(digits) : '')
      setTp3(scaleOut ? (price - 3 * rDist).toFixed(digits) : '')
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

  // Lot to trade: an explicit manual override, else the calculator's result.
  const effectiveLot = (): number | null => {
    const m = parseFloat(manualLot)
    if (m && m > 0) return m
    if (lotCalc && !lotCalc.error && lotCalc.lot_size > 0) return lotCalc.lot_size
    return null
  }

  // Resolve a lot to trade even if the user never clicked "Calculate Lot":
  // fall back to computing it inline from SL + risk %, so the order isn't
  // silently blocked.
  const resolveLot = async (): Promise<number | null> => {
    const existing = effectiveLot()
    if (existing) return existing
    const sl = parseFloat(stopLoss)
    if (!sl || sl <= 0) return null
    try {
      const res = await ordersApi.calculateLot({
        symbol,
        entry_price: entryPrice ? parseFloat(entryPrice) : undefined,
        stop_loss: sl,
        account_balance: parseFloat(accountBalance),
        risk_pct: parseFloat(riskPct),
      })
      if (res.data && !res.data.error && res.data.lot_size > 0) {
        setLotCalc(res.data)
        return res.data.lot_size
      }
    } catch { /* fall through to the error below */ }
    return null
  }

  const placeMt5Order = async () => {
    const sl = stopLoss ? parseFloat(stopLoss) : undefined
    const tp = tp1 ? parseFloat(tp1) : undefined  // a single MT5 position carries one TP
    // All TPs the user set, in order — used for scaled (staged) profit-booking.
    const allTps = [tp1, tp2, tp3].map((t) => parseFloat(t)).filter((t) => t && t > 0)
    const lot = await resolveLot()
    if (!lot) {
      setError('Enter a stop loss (used to auto-size the lot) or type a lot size in the manual field.')
      return
    }
    const direction = side === 'BUY' ? 'long' : 'short'

    // Scale out ONLY when explicitly enabled: one broker position per TP (an MT5
    // position has only one TP). Without the opt-in, a single market order with
    // TP1 is placed — so the user never gets surprise extra positions.
    if (orderType === 'market' && scaleOut && allTps.length >= 2) {
      const res = await mt5Api.scaledTrade({
        symbol, direction, lot_size: lot, take_profits: allTps.join(','), stop_loss: sl,
      })
      const d = res.data || {}
      const tickets = (d.positions || []).filter((p: any) => p.status === 'executed').map((p: any) => p.ticket).join(', ')
      const failed = (d.positions || []).filter((p: any) => p.status === 'failed')
      setSuccess(`✅ Scaled entry: ${d.executed}/${d.legs} positions opened on ${symbol} ${direction} (${d.total_lot} lots total), each exiting at its own TP. Tickets: ${tickets}`)
      if (failed.length) setError(`${failed.length} leg(s) failed: ${failed.map((f: any) => f.error).join('; ')}`)
      mt5.refetch?.()
      return
    }

    if (orderType === 'market') {
      const res = await mt5Api.trade({ symbol, direction, lot_size: lot, stop_loss: sl, take_profit: tp })
      const d = res.data || {}
      const c = d.confirmation || {}
      if (c.confirmed) {
        // Independently read back from MT5 — a verified fill, not just the reply.
        const parts = [
          `✅ Confirmed in MT5: ${symbol} ${direction} ${c.lot_size ?? lot} lots @ ${c.open_price ?? d.price}`,
          `ticket #${c.ticket}`,
        ]
        if (c.sl) parts.push(`SL ${c.sl}`)
        if (c.tp) parts.push(`TP ${c.tp}`)
        setSuccess(parts.join(' · '))
      } else {
        const ref = d.order ? ` (ticket ${d.order})` : ''
        const at = d.price ? ` @ ${d.price}` : ''
        setError(`⚠️ Broker accepted the order${ref}${at}, but it is NOT yet visible in MT5 positions — open your MT5 terminal and verify before doing anything else. (${c.reason || 'read-back inconclusive'})`)
      }
    } else {
      const price = parseFloat(entryPrice)
      if (!price || price <= 0) {
        setError('Entry price is required for a pending (limit/stop) order')
        return
      }
      const res = await mt5Api.pending({
        symbol, direction, order_kind: orderType, volume: lot, price,
        stop_loss: sl, take_profit: tp,
      })
      const d = res.data || {}
      const ref = d.order ? ` (ticket ${d.order})` : ''
      setSuccess(`✅ Live MT5 ${orderType} order placed: ${symbol} ${direction} ${lot} lots @ ${price}${ref}`)
    }
    // Refresh live positions/orders across the app.
    mt5.refetch?.()
  }

  const placeSyntheticOrder = async () => {
    const sl = parseFloat(stopLoss)
    if (!sl || sl <= 0) {
      setError('Stop loss is required')
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
    setSuccess(`Trade planned (ledger): ${res.data.symbol} ${res.data.side} @ ${res.data.quantity} lots — MT5 bridge offline`)
    fetchOpenTrades()
  }

  const placeOrder = async () => {
    setError(null)
    setSuccess(null)
    // Hard gate: never send a real order when the bridge is unreachable or the
    // live data is stale (tunnel down / terminal logged out). Silently falling
    // back to a paper-ledger entry that looks like a fill is the dangerous case.
    if (!mt5.connected) {
      setError('MT5 bridge is offline — order NOT sent. Reconnect the bridge (and confirm the terminal is logged in) before placing real orders.')
      return
    }
    if (mt5.stale) {
      setError('Live MT5 data is stale — the bridge is not responding right now. Order blocked; refresh and confirm the connection is green before retrying.')
      return
    }
    setOrderLoading(true)
    try {
      await placeMt5Order()
      setLotCalc(null)
      setManualLot('')
      setTp1(''); setTp2(''); setTp3(''); setStopLoss('')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Order placement failed')
    } finally {
      setOrderLoading(false)
    }
  }

  const logPaperTrade = async () => {
    setOrderLoading(true); setError(null); setSuccess(null)
    try {
      await placeSyntheticOrder()
      setLotCalc(null); setManualLot('')
      setTp1(''); setTp2(''); setTp3(''); setStopLoss('')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not log paper trade')
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
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Execution Console</h1>
          <p className="text-muted-foreground">Place orders with automatic lot calculation and 1R-based targets</p>
        </div>
        {mt5.connected ? (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Wifi className="w-3.5 h-3.5" />
            Live MT5{mt5.account?.balance ? ` · $${Math.round(mt5.account.balance).toLocaleString()}` : ''}
          </span>
        ) : (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <WifiOff className="w-3.5 h-3.5" />
            Bridge offline · planning to ledger
          </span>
        )}
      </div>

      {/* Connection-health banner — orders are gated on a live, fresh bridge. */}
      {!mt5.connected ? (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            <strong>MT5 bridge {mt5.reachable ? 'reachable but terminal not logged in' : 'offline'}.</strong> Real
            orders are disabled until the connection is restored. {mt5.reachable
              ? 'Log in to the MT5 terminal on the bridge machine.'
              : 'Start/restart the bridge and check the tunnel URL in Settings.'}
          </span>
        </div>
      ) : mt5.stale ? (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span><strong>Live data is stale</strong> — the bridge hasn't responded in ~30s. Orders are blocked until it refreshes green.</span>
        </div>
      ) : (
        <div className="p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-emerald-300/90 text-xs flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>MT5 connected · live (updated {mt5.lastUpdated ? new Date(mt5.lastUpdated).toLocaleTimeString() : '—'})</span>
        </div>
      )}

      {mt5.connected && (
        <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-emerald-300/90 text-xs">
          Orders below are sent <strong>directly to your MT5 account</strong>. Market orders fill immediately;
          limit/stop orders rest as pending until price is reached. By default <strong>one order</strong> is placed at TP1;
          tick <strong>Scale out</strong> to split the lot into one position per target (each exits at its own TP), since a
          single MT5 position can only hold one take-profit. Guardrails (symbol allow-list, max lot, side-aware SL/TP) are enforced server-side.
        </div>
      )}

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
                  {availableInstruments.map((s) => (
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

            <div className="space-y-2">
              <label className="text-sm font-medium">Order Type</label>
              <div className="flex gap-2">
                {(['market', 'limit', 'stop'] as OrderType[]).map((ot) => (
                  <button
                    key={ot}
                    onClick={() => setOrderType(ot)}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium capitalize ${
                      orderType === ot ? 'bg-primary text-primary-foreground' : 'border bg-background'
                    }`}
                  >
                    {ot}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {orderType === 'market'
                  ? 'Fills now at the current market price.'
                  : `Rests as a pending ${orderType} order at your entry price.`}
              </p>
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

            {orderType === 'market' && (
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={scaleOut}
                  onChange={(e) => {
                    const on = e.target.checked
                    setScaleOut(on)
                    // Fill or clear TP2/TP3 to match what will actually be placed.
                    const ep = parseFloat(entryPrice)
                    if (ep > 0) {
                      const rDist = getRDistance(symbol, ep)
                      const digits = symbol === 'BTCUSD' ? 0 : symbol === 'USDJPY' ? 3 : symbol === 'EURUSD' || symbol === 'GBPUSD' ? 5 : 2
                      const sign = side === 'BUY' ? 1 : -1
                      setTp2(on ? (ep + sign * 2 * rDist).toFixed(digits) : '')
                      setTp3(on ? (ep + sign * 3 * rDist).toFixed(digits) : '')
                    }
                  }}
                />
                <span>
                  <strong>Scale out</strong> — split the lot into one position per TP (opens multiple orders).
                  {scaleOut ? ' On: TP1/TP2/TP3 each get their own position.' : ' Off: one order at TP1.'}
                </span>
              </label>
            )}

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
              <label className="text-sm font-medium">Lot Size (manual override)</label>
              <input
                type="number"
                step="0.01"
                value={manualLot}
                onChange={(e) => setManualLot(e.target.value)}
                placeholder={lotCalc && !lotCalc.error ? `Calculated: ${lotCalc.lot_size.toFixed(2)}` : 'Leave blank to use calculator'}
                className="w-full px-3 py-2 border rounded-md bg-background"
              />
              <p className="text-xs text-muted-foreground">
                {effectiveLot() ? `Will trade ${effectiveLot()} lots` : 'Calculate a lot size or enter one to enable MT5 order'}
              </p>
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
              {mt5.connected && !mt5.stale ? (
                <Button
                  onClick={placeOrder}
                  disabled={orderLoading}
                  className="flex-1"
                >
                  <Zap className="w-4 h-4 mr-2" />
                  {orderLoading ? 'Placing…' : `Send ${orderType} to MT5`}
                </Button>
              ) : (
                <div className="flex-1 flex flex-col gap-1">
                  <Button disabled className="w-full" title="Bridge offline — reconnect to place real orders">
                    <Zap className="w-4 h-4 mr-2" />
                    {mt5.stale ? 'Bridge not responding' : 'Bridge offline'}
                  </Button>
                  <button
                    onClick={logPaperTrade}
                    disabled={orderLoading}
                    className="text-[11px] text-muted-foreground underline hover:text-foreground"
                  >
                    Log as paper trade instead (not sent to broker)
                  </button>
                </div>
              )}
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

                  <div className="p-2 rounded bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-400 flex items-center justify-between gap-2">
                    <span><Shield className="w-3 h-3 inline mr-1" />Tick size: {lotCalc.tick_size}, Tick value: ${lotCalc.tick_value}</span>
                    <span className={`px-1.5 py-0.5 rounded font-medium ${lotCalc.rate_source === 'mt5' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'}`}>
                      {lotCalc.rate_source === 'mt5' ? 'sized from MT5 rates' : 'static rates'}
                    </span>
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

      {/* Live MT5 positions with full management (close / partial / modify SL-TP) */}
      {mt5.connected && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Wifi className="w-4 h-4 text-emerald-400" />
              Live MT5 Positions
            </CardTitle>
            <div className="text-sm text-muted-foreground">
              {mt5.positions.length} open · float{' '}
              <span className={mt5.totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {mt5.totalProfit >= 0 ? '+' : ''}{mt5.totalProfit.toFixed(2)}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <Mt5PositionsPanel variant="full" />
          </CardContent>
        </Card>
      )}

      {/* Ledger open trades (planning fallback when the bridge is offline) */}
      {!mt5.connected && (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Open Trades (ledger)</CardTitle>
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
      )}
    </div>
  )
}
