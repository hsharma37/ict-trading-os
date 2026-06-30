import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { mt5Api } from '@/api/client'
import {
  Monitor, Wifi, WifiOff, TrendingUp, TrendingDown,
  RefreshCw, Send, X, History, Briefcase, Loader2
} from 'lucide-react'

interface MT5Account {
  balance: number
  equity: number
  margin: number
  free_margin: number
  margin_level: number
  status?: string
}

interface MT5Position {
  ticket: string
  symbol: string
  direction: string
  lot_size: number
  open_price: number
  current_price?: number
  sl: number
  tp: number
  profit: number
  swap: number
}

interface MT5HistoryTrade {
  ticket: string
  symbol: string
  direction: string
  lot_size: number
  open_price: number
  close_price: number
  profit: number
  closed_at: string
}

export default function MT5Terminal() {
  const [connected, setConnected] = useState(false)
  const [account, setAccount] = useState<MT5Account | null>(null)
  const [positions, setPositions] = useState<MT5Position[]>([])
  const [history, setHistory] = useState<MT5HistoryTrade[]>([])
  const [loading, setLoading] = useState(false)
  const [tradeForm, setTradeForm] = useState({
    symbol: 'EURUSD',
    direction: 'long',
    lot_size: 0.1,
    stop_loss: '',
    take_profit: '',
  })
  const [tradeLoading, setTradeLoading] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setLastError(null)
    try {
      const [statusRes, accountRes, posRes, histRes] = await Promise.allSettled([
        mt5Api.status(),
        mt5Api.account(),
        mt5Api.positions(),
        mt5Api.history(),
      ])

      const status = statusRes.status === 'fulfilled' ? statusRes.value.data : null
      setConnected(!!status?.reachable)

      if (accountRes.status === 'fulfilled') {
        setAccount(accountRes.value.data)
      }
      if (posRes.status === 'fulfilled') {
        const posData = posRes.value.data
        setPositions(posData.positions || [])
      }
      if (histRes.status === 'fulfilled') {
        const histData = histRes.value.data
        setHistory(histData.history || [])
      }

      if (statusRes.status === 'rejected') {
        setLastError('MT5 bridge not reachable. Ensure the bridge is running on port 5001.')
      }
    } catch (e: any) {
      setLastError(e?.message || 'Error fetching MT5 data')
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 5000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const handleTrade = async () => {
    setTradeLoading(true)
    try {
      const payload = {
        symbol: tradeForm.symbol,
        direction: tradeForm.direction,
        lot_size: Number(tradeForm.lot_size),
        stop_loss: tradeForm.stop_loss ? Number(tradeForm.stop_loss) : undefined,
        take_profit: tradeForm.take_profit ? Number(tradeForm.take_profit) : undefined,
      }
      await mt5Api.trade(payload)
      await fetchAll()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Trade failed')
    } finally {
      setTradeLoading(false)
    }
  }

  const handleClose = async (ticketId: string) => {
    try {
      await mt5Api.close({ ticket_id: ticketId })
      await fetchAll()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Close failed')
    }
  }

  const marginLevel = account?.margin_level ?? 0
  const marginSafe = marginLevel > 200 || marginLevel === 0
  const marginWarning = marginLevel > 100 && marginLevel <= 200

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Monitor className="w-6 h-6 text-primary" />
            MT5 Terminal
          </h1>
          <p className="text-muted-foreground">Live MT5 account, positions, and trade execution</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-border">
            {connected ? (
              <>
                <Wifi className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-emerald-400 font-medium">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-red-400" />
                <span className="text-xs text-red-400 font-medium">Disconnected</span>
              </>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {lastError && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <X className="w-4 h-4" />
          {lastError}
        </div>
      )}

      {/* Account Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Balance</div>
            <div className="text-lg font-bold font-mono">${account?.balance?.toFixed(2) ?? '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Equity</div>
            <div className="text-lg font-bold font-mono">${account?.equity?.toFixed(2) ?? '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Margin</div>
            <div className="text-lg font-bold font-mono">${account?.margin?.toFixed(2) ?? '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Free Margin</div>
            <div className="text-lg font-bold font-mono">${account?.free_margin?.toFixed(2) ?? '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Margin Level</div>
            <div className="text-lg font-bold font-mono">
              {account?.margin_level ? `${account.margin_level.toFixed(1)}%` : '-'}
            </div>
            {account?.margin_level !== undefined && (
              <div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full ${marginSafe ? 'bg-emerald-400' : marginWarning ? 'bg-amber-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.min(marginLevel, 100)}%` }}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Open Positions */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Briefcase className="w-5 h-5 text-primary" />
                Open Positions
                <span className="text-xs text-muted-foreground font-normal ml-auto">
                  Auto-refresh every 5s
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {positions.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  No open positions.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-2 text-xs font-medium text-muted-foreground">Symbol</th>
                        <th className="text-left p-2 text-xs font-medium text-muted-foreground">Dir</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Lots</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Open</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Current</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">SL</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">TP</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Profit</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Swap</th>
                        <th className="p-2 text-xs font-medium text-muted-foreground"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((pos) => {
                        const profit = pos.profit ?? 0
                        const positive = profit >= 0
                        return (
                          <tr key={pos.ticket} className="border-b border-border/50 hover:bg-muted/30">
                            <td className="p-2 font-medium">{pos.symbol}</td>
                            <td className="p-2">
                              <span className={`inline-flex items-center gap-1 text-xs font-medium ${pos.direction === 'long' ? 'text-emerald-400' : 'text-red-400'}`}>
                                {pos.direction === 'long' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {pos.direction.toUpperCase()}
                              </span>
                            </td>
                            <td className="p-2 text-right font-mono">{pos.lot_size}</td>
                            <td className="p-2 text-right font-mono">{pos.open_price?.toFixed(5)}</td>
                            <td className="p-2 text-right font-mono">{pos.current_price?.toFixed(5) ?? '-'}</td>
                            <td className="p-2 text-right font-mono">{pos.sl?.toFixed(5) ?? '-'}</td>
                            <td className="p-2 text-right font-mono">{pos.tp?.toFixed(5) ?? '-'}</td>
                            <td className={`p-2 text-right font-mono font-semibold ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                              {positive ? '+' : ''}{profit.toFixed(2)}
                            </td>
                            <td className="p-2 text-right font-mono">{pos.swap?.toFixed(2) ?? '0.00'}</td>
                            <td className="p-2">
                              <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={() => handleClose(pos.ticket)}>
                                <X className="w-3 h-3 mr-1" /> Close
                              </Button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Trade History */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="w-5 h-5 text-primary" />
                Trade History
              </CardTitle>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  No closed trades yet.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-2 text-xs font-medium text-muted-foreground">Symbol</th>
                        <th className="text-left p-2 text-xs font-medium text-muted-foreground">Dir</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Lots</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Open</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">Close</th>
                        <th className="text-right p-2 text-xs font-medium text-muted-foreground">P&L</th>
                        <th className="text-left p-2 text-xs font-medium text-muted-foreground">Closed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(0, 20).map((h) => {
                        const profit = h.profit ?? 0
                        const positive = profit >= 0
                        return (
                          <tr key={h.ticket} className="border-b border-border/50 hover:bg-muted/30">
                            <td className="p-2 font-medium">{h.symbol}</td>
                            <td className="p-2">
                              <span className={`text-xs font-medium ${h.direction === 'long' ? 'text-emerald-400' : 'text-red-400'}`}>
                                {h.direction.toUpperCase()}
                              </span>
                            </td>
                            <td className="p-2 text-right font-mono">{h.lot_size}</td>
                            <td className="p-2 text-right font-mono">{h.open_price?.toFixed(5)}</td>
                            <td className="p-2 text-right font-mono">{h.close_price?.toFixed(5)}</td>
                            <td className={`p-2 text-right font-mono font-semibold ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                              {positive ? '+' : ''}{profit.toFixed(2)}
                            </td>
                            <td className="p-2 text-xs text-muted-foreground">
                              {h.closed_at ? new Date(h.closed_at).toLocaleString() : '-'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Trade Panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Send className="w-5 h-5 text-primary" />
                Quick Trade
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Symbol</label>
                <select
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                  value={tradeForm.symbol}
                  onChange={(e) => setTradeForm({ ...tradeForm, symbol: e.target.value })}
                >
                  {['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD', 'NQ1!', 'ES1!', 'CL1!'].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Direction</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setTradeForm({ ...tradeForm, direction: 'long' })}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border transition-colors ${
                      tradeForm.direction === 'long'
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <TrendingUp className="w-4 h-4 inline mr-1" /> Long
                  </button>
                  <button
                    onClick={() => setTradeForm({ ...tradeForm, direction: 'short' })}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border transition-colors ${
                      tradeForm.direction === 'short'
                        ? 'bg-red-500/10 border-red-500/30 text-red-400'
                        : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <TrendingDown className="w-4 h-4 inline mr-1" /> Short
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Lot Size</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                  value={tradeForm.lot_size}
                  onChange={(e) => setTradeForm({ ...tradeForm, lot_size: Number(e.target.value) })}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Stop Loss</label>
                  <input
                    type="number"
                    step="0.00001"
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                    placeholder="Optional"
                    value={tradeForm.stop_loss}
                    onChange={(e) => setTradeForm({ ...tradeForm, stop_loss: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Take Profit</label>
                  <input
                    type="number"
                    step="0.00001"
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                    placeholder="Optional"
                    value={tradeForm.take_profit}
                    onChange={(e) => setTradeForm({ ...tradeForm, take_profit: e.target.value })}
                  />
                </div>
              </div>

              <Button
                className="w-full"
                onClick={handleTrade}
                disabled={tradeLoading || !connected}
              >
                {tradeLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                Send to MT5
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 space-y-3">
              <div className="text-xs font-medium text-muted-foreground">Account Status</div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <span className={connected ? 'text-emerald-400' : 'text-red-400'}>
                    {connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Bridge</span>
                  <span className="font-mono text-xs">http://localhost:5001</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Positions</span>
                  <span className="font-mono">{positions.length}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
