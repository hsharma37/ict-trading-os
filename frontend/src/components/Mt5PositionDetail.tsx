import { Button } from '@/components/ui/Button'
import { useMt5, Mt5Position } from '@/hooks/useMt5'
import {
  Crosshair, TrendingUp, TrendingDown, DollarSign, Percent, MoveRight,
} from 'lucide-react'

function pipSize(symbol: string): number {
  if (symbol === 'XAUUSD' || symbol === 'CL1!' || symbol === 'USDJPY') return 0.01
  return 0.0001
}
function pips(a: number, b: number, symbol: string): number {
  return Math.round(Math.abs(a - b) / pipSize(symbol))
}

/**
 * Rich single-position visualization for a live MT5 position — the broker-feed
 * equivalent of the internal-trade detail view on What's Up: live price banner,
 * SL→entry→TP progress bar, pip distances, a price ladder, a metrics grid, and
 * inline management (modify SL/TP, partial, close) via the shared useMt5 hook.
 */
export default function Mt5PositionDetail({ position: p }: { position: Mt5Position }) {
  const { close, modify, partialClose } = useMt5()
  const busy = close.isPending || modify.isPending || partialClose.isPending

  const cur = p.current_price ?? p.open_price
  const isLong = p.direction === 'long'
  const priceChange = cur - p.open_price
  const dir = priceChange > 0 ? 'up' : priceChange < 0 ? 'down' : 'flat'
  const digits = p.symbol === 'XAUUSD' || p.symbol === 'USDJPY' || p.symbol === 'CL1!' ? 2 : 5

  const range = p.tp && p.sl ? p.tp - p.sl : 0
  const clampPct = (v: number) => Math.max(0, Math.min(100, v))
  const pct = range ? clampPct(((cur - p.sl) / range) * 100) : 50
  const entryPct = range ? clampPct(((p.open_price - p.sl) / range) * 100) : 50

  const onClose = () => { if (window.confirm(`Close ${p.symbol} ${p.direction} ${p.lot_size} lots at market?`)) close.mutate(p.ticket) }
  const onModify = () => {
    const sl = window.prompt(`New Stop Loss for ${p.symbol} (blank keeps ${p.sl ?? '-'})`, String(p.sl ?? ''))
    if (sl === null) return
    const tp = window.prompt(`New Take Profit for ${p.symbol} (blank keeps ${p.tp ?? '-'})`, String(p.tp ?? ''))
    if (tp === null) return
    modify.mutate({ ticket: p.ticket, stop_loss: sl ? Number(sl) : undefined, take_profit: tp ? Number(tp) : undefined })
  }
  const onPartial = () => {
    const raw = window.prompt(`Volume to close for ${p.symbol} (max ${p.lot_size})`, String((p.lot_size || 0) / 2))
    if (raw === null) return
    const vol = Number(raw)
    if (!vol || vol <= 0 || vol > (p.lot_size || 0)) { alert(`Enter a volume between 0 and ${p.lot_size}`); return }
    partialClose.mutate({ ticket: p.ticket, volume: vol })
  }

  const ladderRow = (label: string, value: number | undefined, color: string, filled = false) => (
    <div className="flex items-center gap-2">
      <div className={`w-20 text-xs ${color} font-medium text-right`}>{label}</div>
      <div className={`flex-1 h-3 rounded ${filled ? color.replace('text-', 'bg-') : 'bg-muted'} relative`}>
        {filled && <div className="absolute inset-0 flex items-center justify-center"><div className={`w-3 h-3 rounded-full bg-white border-2 ${color.replace('text-', 'border-')}`}></div></div>}
      </div>
      <div className="w-24 text-xs font-mono font-bold text-right">{value != null ? value.toFixed(digits) : '-'}</div>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card p-4">
        {/* Header */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <Crosshair className="w-5 h-5" />
          <span className="font-bold text-lg">{p.symbol}</span>
          <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${isLong ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
            {isLong ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {p.direction.toUpperCase()}
          </span>
          <span className="text-xs text-muted-foreground">{p.lot_size} lots</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">MT5 broker feed</span>
        </div>

        {/* Live price banner */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted mb-4">
          <div>
            <div className="text-xs text-muted-foreground">Live Price</div>
            <div className="text-2xl font-bold font-mono flex items-center gap-2">
              {cur.toFixed(digits)}
              {dir === 'up' && <TrendingUp className="w-5 h-5 text-green-400" />}
              {dir === 'down' && <TrendingDown className="w-5 h-5 text-red-400" />}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground">vs Entry</div>
            <div className={`text-lg font-semibold ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(digits)}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {range !== 0 && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Price Progress</span>
              <span className="text-xs text-muted-foreground">{pct.toFixed(1)}% toward TP</span>
            </div>
            <div className="relative h-6 bg-muted rounded-full overflow-hidden">
              <div className="absolute left-0 top-0 h-full w-0.5 bg-red-500 z-10" />
              <div className="absolute top-0 h-full w-0.5 bg-blue-500 z-10" style={{ left: `${entryPct}%` }} />
              <div className="absolute right-0 top-0 h-full w-0.5 bg-green-500 z-10" />
              <div className={`absolute left-0 top-0 h-full ${isLong ? 'bg-green-400/50' : 'bg-red-400/50'}`} style={{ width: `${pct}%` }} />
              <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-purple-500 z-20" style={{ left: `calc(${pct}% - 6px)` }} />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
              <span>SL {p.sl}</span>
              <span>Entry {p.open_price}</span>
              <span>TP {p.tp}</span>
            </div>
          </div>
        )}

        {/* Distance to levels */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="p-2 rounded-lg bg-red-50 border border-red-200">
            <div className="text-[10px] text-red-600 font-medium">Distance to SL</div>
            <div className="text-sm font-bold text-red-600">{p.sl ? pips(cur, p.sl, p.symbol) : '-'} pips</div>
          </div>
          <div className="p-2 rounded-lg bg-green-50 border border-green-200">
            <div className="text-[10px] text-green-600 font-medium">Distance to TP</div>
            <div className="text-sm font-bold text-green-600">{p.tp ? pips(cur, p.tp, p.symbol) : '-'} pips</div>
          </div>
        </div>

        {/* Price ladder */}
        <div className="mb-6">
          <div className="text-sm font-medium mb-2">Price Ladder</div>
          <div className="space-y-1">
            {ladderRow('TP', p.tp, 'text-green-400')}
            {isLong ? ladderRow('Entry', p.open_price, 'text-blue-400', true) : ladderRow('Current', cur, 'text-purple-400', true)}
            {isLong ? ladderRow('Current', cur, 'text-purple-400', true) : ladderRow('Entry', p.open_price, 'text-blue-400', true)}
            {ladderRow('SL', p.sl, 'text-red-400')}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2 mb-4">
          <Button size="sm" variant="outline" className="text-xs" disabled={busy} onClick={onModify}>
            <MoveRight className="w-3 h-3 mr-1" /> Modify SL/TP
          </Button>
          <Button size="sm" variant="outline" className="text-xs text-green-600" disabled={busy} onClick={onPartial}>
            <Percent className="w-3 h-3 mr-1" /> Partial Close
          </Button>
          <Button size="sm" variant="default" className="text-xs" disabled={busy} onClick={onClose}>
            <DollarSign className="w-3 h-3 mr-1" /> Close Full
          </Button>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { k: 'Profit', v: `$${(p.profit ?? 0).toFixed(2)}`, c: (p.profit ?? 0) >= 0 ? 'text-green-400' : 'text-red-400' },
            { k: 'Swap', v: `$${(p.swap ?? 0).toFixed(2)}` },
            { k: 'Lots', v: String(p.lot_size) },
            { k: 'Open', v: p.open_price?.toFixed(digits) },
            { k: 'Current', v: cur.toFixed(digits) },
            { k: 'Ticket', v: `#${p.ticket}` },
          ].map((m) => (
            <div key={m.k} className="p-3 rounded-lg bg-muted">
              <div className="text-xs text-muted-foreground">{m.k}</div>
              <div className={`font-semibold ${m.c || ''}`}>{m.v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
