import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { mt5Api } from '@/api/client'
import { useMt5 } from '@/hooks/useMt5'
import Mt5PositionsPanel from '@/components/Mt5PositionsPanel'
import {
  Monitor, Wifi, WifiOff, TrendingUp, TrendingDown,
  RefreshCw, Send, History, Briefcase, Loader2,
} from 'lucide-react'

export default function MT5Terminal() {
  const { connected, account, history, refetch } = useMt5()
  const [tradeForm, setTradeForm] = useState({
    symbol: 'EURUSD',
    direction: 'long',
    lot_size: 0.1,
    stop_loss: '',
    take_profit: '',
  })
  const [tradeLoading, setTradeLoading] = useState(false)

  const handleTrade = async () => {
    setTradeLoading(true)
    try {
      await mt5Api.trade({
        symbol: tradeForm.symbol,
        direction: tradeForm.direction,
        lot_size: Number(tradeForm.lot_size),
        stop_loss: tradeForm.stop_loss ? Number(tradeForm.stop_loss) : undefined,
        take_profit: tradeForm.take_profit ? Number(tradeForm.take_profit) : undefined,
      })
      refetch()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Trade failed')
    } finally {
      setTradeLoading(false)
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
              <><Wifi className="w-4 h-4 text-emerald-400" /><span className="text-xs text-emerald-400 font-medium">Connected</span></>
            ) : (
              <><WifiOff className="w-4 h-4 text-red-400" /><span className="text-xs text-red-400 font-medium">Disconnected</span></>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Account Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Balance', val: account?.balance },
          { label: 'Equity', val: account?.equity },
          { label: 'Margin', val: account?.margin },
          { label: 'Free Margin', val: account?.free_margin },
        ].map((c) => (
          <Card key={c.label}>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">{c.label}</div>
              <div className="text-lg font-bold font-mono">${c.val?.toFixed(2) ?? '-'}</div>
            </CardContent>
          </Card>
        ))}
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Margin Level</div>
            <div className="text-lg font-bold font-mono">{account?.margin_level ? `${account.margin_level.toFixed(1)}%` : '-'}</div>
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
        <div className="lg:col-span-2 space-y-4">
          {/* Open Positions (shared panel — same source as Dashboard + What's Up) */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Briefcase className="w-5 h-5 text-primary" />
                Open Positions
                <span className="text-xs text-muted-foreground font-normal ml-auto">Auto-refresh every 5s</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Mt5PositionsPanel variant="full" />
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
                <div className="text-center text-muted-foreground py-8">No closed trades yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        {['Symbol', 'Dir', 'Lots', 'Open', 'Close', 'P&L', 'Closed'].map((h, i) => (
                          <th key={h} className={`p-2 text-xs font-medium text-muted-foreground ${i < 2 ? 'text-left' : i === 6 ? 'text-left' : 'text-right'}`}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(0, 20).map((h: any) => {
                        const positive = (h.profit ?? 0) >= 0
                        return (
                          <tr key={h.ticket} className="border-b border-border/50 hover:bg-muted/30">
                            <td className="p-2 font-medium">{h.symbol}</td>
                            <td className="p-2">
                              <span className={`text-xs font-medium ${h.direction === 'long' ? 'text-emerald-400' : 'text-red-400'}`}>
                                {(h.direction || '-').toUpperCase()}
                              </span>
                            </td>
                            <td className="p-2 text-right font-mono">{h.lot_size}</td>
                            <td className="p-2 text-right font-mono">{h.open_price?.toFixed(5)}</td>
                            <td className="p-2 text-right font-mono">{h.close_price?.toFixed(5)}</td>
                            <td className={`p-2 text-right font-mono font-semibold ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                              {positive ? '+' : ''}{(h.profit ?? 0).toFixed(2)}
                            </td>
                            <td className="p-2 text-xs text-muted-foreground">{h.closed_at ? new Date(h.closed_at).toLocaleString() : '-'}</td>
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
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border transition-colors ${tradeForm.direction === 'long' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'border-border bg-muted text-muted-foreground hover:text-foreground'}`}
                  >
                    <TrendingUp className="w-4 h-4 inline mr-1" /> Long
                  </button>
                  <button
                    onClick={() => setTradeForm({ ...tradeForm, direction: 'short' })}
                    className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border transition-colors ${tradeForm.direction === 'short' ? 'bg-red-500/10 border-red-500/30 text-red-400' : 'border-border bg-muted text-muted-foreground hover:text-foreground'}`}
                  >
                    <TrendingDown className="w-4 h-4 inline mr-1" /> Short
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Lot Size</label>
                <input
                  type="number" step="0.01" min="0.01"
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                  value={tradeForm.lot_size}
                  onChange={(e) => setTradeForm({ ...tradeForm, lot_size: Number(e.target.value) })}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Stop Loss</label>
                  <input
                    type="number" step="0.00001" placeholder="Optional"
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                    value={tradeForm.stop_loss}
                    onChange={(e) => setTradeForm({ ...tradeForm, stop_loss: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Take Profit</label>
                  <input
                    type="number" step="0.00001" placeholder="Optional"
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm font-mono"
                    value={tradeForm.take_profit}
                    onChange={(e) => setTradeForm({ ...tradeForm, take_profit: e.target.value })}
                  />
                </div>
              </div>

              <Button className="w-full" onClick={handleTrade} disabled={tradeLoading || !connected}>
                {tradeLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                Send to MT5
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
