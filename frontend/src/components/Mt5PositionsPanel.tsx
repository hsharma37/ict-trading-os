import { Button } from '@/components/ui/Button'
import { useMt5, Mt5Position } from '@/hooks/useMt5'
import { TrendingUp, TrendingDown, X, WifiOff } from 'lucide-react'

type Variant = 'full' | 'compact' | 'visual'

/**
 * Live MT5 open positions + order management, backed by the shared useMt5
 * hook. Rendered on the MT5 Terminal ('full'), Dashboard ('compact') and
 * What's Up ('visual') pages, so all three show the same positions and the
 * same close/modify/partial actions work identically everywhere.
 */
export default function Mt5PositionsPanel({
  variant = 'full', limit, onSelect, selectedTicket,
}: {
  variant?: Variant; limit?: number
  onSelect?: (ticket: string) => void
  selectedTicket?: string
}) {
  const { connected, positions, close, modify, partialClose } = useMt5()

  const busy = close.isPending || modify.isPending || partialClose.isPending

  const onClose = (p: Mt5Position) => {
    if (window.confirm(`Close ${p.symbol} ${p.direction} ${p.lot_size} lots at market?`)) {
      close.mutate(p.ticket)
    }
  }
  const onModify = (p: Mt5Position) => {
    const sl = window.prompt(`New Stop Loss for ${p.symbol} (blank keeps ${p.sl ?? '-'})`, String(p.sl ?? ''))
    if (sl === null) return
    const tp = window.prompt(`New Take Profit for ${p.symbol} (blank keeps ${p.tp ?? '-'})`, String(p.tp ?? ''))
    if (tp === null) return
    modify.mutate({ ticket: p.ticket, stop_loss: sl ? Number(sl) : undefined, take_profit: tp ? Number(tp) : undefined })
  }
  const onPartial = (p: Mt5Position) => {
    const raw = window.prompt(`Volume to close for ${p.symbol} (max ${p.lot_size})`, String((p.lot_size || 0) / 2))
    if (raw === null) return
    const vol = Number(raw)
    if (!vol || vol <= 0 || vol > (p.lot_size || 0)) {
      alert(`Enter a volume between 0 and ${p.lot_size}`)
      return
    }
    partialClose.mutate({ ticket: p.ticket, volume: vol })
  }

  const shown = limit ? positions.slice(0, limit) : positions

  if (!connected && positions.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
        <WifiOff className="w-4 h-4 text-red-400" /> MT5 bridge not connected
      </div>
    )
  }
  if (positions.length === 0) {
    return <div className="text-center text-muted-foreground text-sm py-6">No open MT5 positions.</div>
  }

  const dirBadge = (p: Mt5Position) => (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${p.direction === 'long' ? 'text-emerald-400' : 'text-red-400'}`}>
      {p.direction === 'long' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {(p.direction || '-').toUpperCase()}
    </span>
  )
  const pnl = (p: Mt5Position) => (
    <span className={`font-mono font-semibold ${(p.profit ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
      {(p.profit ?? 0) >= 0 ? '+' : ''}{(p.profit ?? 0).toFixed(2)}
    </span>
  )

  // Compact: tidy rows for the Dashboard.
  if (variant === 'compact') {
    return (
      <div className="space-y-2">
        {shown.map((p) => (
          <div key={p.ticket} className="flex items-center justify-between p-2 rounded bg-muted gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {dirBadge(p)}
              <span className="font-semibold text-sm truncate">{p.symbol}</span>
              <span className="text-xs text-muted-foreground">{p.lot_size}</span>
            </div>
            <div className="flex items-center gap-3">
              {pnl(p)}
              <Button size="sm" variant="outline" className="h-6 px-2 text-xs" disabled={busy} onClick={() => onClose(p)}>
                Close
              </Button>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Visual: SL -> entry -> TP progress bar per position, for What's Up.
  if (variant === 'visual') {
    return (
      <div className="space-y-3">
        {shown.map((p) => {
          const cur = p.current_price ?? p.open_price
          const range = p.tp && p.sl ? p.tp - p.sl : 0
          const pct = range ? Math.max(0, Math.min(100, ((cur - p.sl) / range) * 100)) : 50
          const entryPct = range ? Math.max(0, Math.min(100, ((p.open_price - p.sl) / range) * 100)) : 50
          return (
            <div
              key={p.ticket}
              onClick={onSelect ? () => onSelect(p.ticket) : undefined}
              className={`p-3 rounded-xl border bg-card transition-all ${
                onSelect ? 'cursor-pointer hover:bg-muted/50' : ''
              } ${selectedTicket === p.ticket ? 'border-primary ring-1 ring-primary/30' : 'border-border'}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {dirBadge(p)}
                  <span className="font-bold">{p.symbol}</span>
                  <span className="text-xs text-muted-foreground">{p.lot_size} lots</span>
                </div>
                {pnl(p)}
              </div>
              {range !== 0 && (
                <div className="relative h-5 bg-muted rounded-full overflow-hidden mb-1">
                  <div className="absolute left-0 top-0 h-full w-0.5 bg-red-500 z-10" title="SL" />
                  <div className="absolute top-0 h-full w-0.5 bg-blue-500 z-10" style={{ left: `${entryPct}%` }} title="Entry" />
                  <div className="absolute right-0 top-0 h-full w-0.5 bg-green-500 z-10" title="TP" />
                  <div className={`absolute left-0 top-0 h-full ${p.direction === 'long' ? 'bg-emerald-400/40' : 'bg-red-400/40'}`} style={{ width: `${pct}%` }} />
                  <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-purple-500 z-20" style={{ left: `calc(${pct}% - 6px)` }} />
                </div>
              )}
              <div className="flex justify-between text-[10px] text-muted-foreground mb-2">
                <span>SL {p.sl || '-'}</span>
                <span>Entry {p.open_price}</span>
                <span>Now {cur?.toFixed?.(2) ?? cur}</span>
                <span>TP {p.tp || '-'}</span>
              </div>
              <div className="flex flex-wrap gap-1 justify-end">
                <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onModify(p)}>SL/TP</Button>
                <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onPartial(p)}>Partial</Button>
                <Button size="sm" variant="default" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onClose(p)}>Close</Button>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Full: table for the MT5 Terminal.
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {['Symbol', 'Dir', 'Lots', 'Open', 'Current', 'SL', 'TP', 'Profit', 'Swap', ''].map((h) => (
              <th key={h} className={`p-2 text-xs font-medium text-muted-foreground ${h === 'Symbol' || h === 'Dir' ? 'text-left' : 'text-right'}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((p) => (
            <tr key={p.ticket} className="border-b border-border/50 hover:bg-muted/30">
              <td className="p-2 font-medium">{p.symbol}</td>
              <td className="p-2">{dirBadge(p)}</td>
              <td className="p-2 text-right font-mono">{p.lot_size}</td>
              <td className="p-2 text-right font-mono">{p.open_price?.toFixed(5)}</td>
              <td className="p-2 text-right font-mono">{p.current_price?.toFixed(5) ?? '-'}</td>
              <td className="p-2 text-right font-mono">{p.sl?.toFixed(5) ?? '-'}</td>
              <td className="p-2 text-right font-mono">{p.tp?.toFixed(5) ?? '-'}</td>
              <td className="p-2 text-right">{pnl(p)}</td>
              <td className="p-2 text-right font-mono">{p.swap?.toFixed(2) ?? '0.00'}</td>
              <td className="p-2">
                <div className="flex items-center gap-1 justify-end">
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onModify(p)} title="Modify SL/TP">SL/TP</Button>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onPartial(p)} title="Partial close">Partial</Button>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => onClose(p)}>
                    <X className="w-3 h-3 mr-1" /> Close
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!connected && (
        <div className="flex items-center gap-1 text-xs text-amber-500 mt-2">
          <WifiOff className="w-3 h-3" /> Showing last-known positions — MT5 bridge not currently reachable.
        </div>
      )}
    </div>
  )
}
