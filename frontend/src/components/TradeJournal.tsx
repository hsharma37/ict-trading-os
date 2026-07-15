import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { journalApi } from '@/api/client'
import { BookOpen, RefreshCw, DownloadCloud } from 'lucide-react'

interface JournalTrade {
  id: string; symbol: string; side: string; direction: string; lot_size: number
  open_price: number; close_price: number; profit: number; profit_norm?: number; r: number | null; closed_at: string
  note?: string
}
interface Summary {
  symbol: string; closed_trades: number; winning_trades: number; losing_trades: number
  win_rate: number; total_pnl: number; avg_pnl: number; best_trade: number; worst_trade: number
  total_r: number; avg_r: number; r_tracked_trades: number; stats_basis?: string
}
interface SymRow { symbol: string; trades: number; total_pnl: number }

const money = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}`

export default function TradeJournal() {
  const [symbols, setSymbols] = useState<SymRow[]>([])
  const [selected, setSelected] = useState<string>('') // '' = all
  const [trades, setTrades] = useState<JournalTrade[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [symRes, listRes] = await Promise.all([
        journalApi.symbols(),
        journalApi.list(selected || undefined, 300),
      ])
      setSymbols(symRes.data?.symbols || [])
      setTrades(listRes.data?.trades || [])
      setSummary(listRes.data?.summary || null)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [selected])

  useEffect(() => { load() }, [load])

  const syncFromMt5 = async () => {
    setSyncing(true)
    try { await journalApi.sync(); await load() }
    catch { /* ignore */ } finally { setSyncing(false) }
  }

  // Manually fill R for a trade whose stop-loss wasn't captured: enter the SL
  // and R is computed from it (broker rates), or enter R directly.
  const fillR = async (t: JournalTrade) => {
    const sl = window.prompt(`Stop-loss for ${t.symbol} (opened at ${t.open_price}) — R is computed from it.\nLeave blank to enter R directly.`)
    if (sl === null) return
    try {
      if (sl.trim()) {
        await journalApi.setRisk(t.id, { sl: Number(sl) })
      } else {
        const r = window.prompt('Enter the R multiple for this trade (e.g. 1.5 or -1):')
        if (r === null || !r.trim()) return
        await journalApi.setRisk(t.id, { r: Number(r) })
      }
      await load()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Could not set R')
    }
  }

  const stat = (label: string, value: string, cls = '') => (
    <div className="p-2.5 rounded-lg bg-muted">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-base font-bold ${cls}`}>{value}</div>
    </div>
  )

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary" /> Trade Journal
          <span className="text-xs font-normal text-muted-foreground">durable · per instrument</span>
        </CardTitle>
        <div className="flex items-center gap-2">
          <button onClick={syncFromMt5} disabled={syncing}
            className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-muted-foreground hover:text-foreground">
            <DownloadCloud className={`w-3.5 h-3.5 ${syncing ? 'animate-pulse' : ''}`} />
            {syncing ? 'Syncing…' : 'Sync from MT5'}
          </button>
          <button onClick={load} className="text-muted-foreground hover:text-foreground">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Instrument filter */}
        <div className="flex gap-1.5 flex-wrap">
          <button onClick={() => setSelected('')}
            className={`text-xs px-2.5 py-1 rounded-md border ${selected === '' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            All ({symbols.reduce((s, x) => s + x.trades, 0)})
          </button>
          {symbols.map((s) => (
            <button key={s.symbol} onClick={() => setSelected(s.symbol)}
              className={`text-xs px-2.5 py-1 rounded-md border ${selected === s.symbol ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'}`}>
              {s.symbol} ({s.trades}) <span className={s.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>{money(s.total_pnl)}</span>
            </button>
          ))}
        </div>

        {/* Summary for the selection */}
        {summary && (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            {stat('Trades', String(summary.closed_trades))}
            {stat('Win rate', `${summary.win_rate}%`)}
            {stat('Net P&L', money(summary.total_pnl), summary.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}
            {stat('Avg /lot', money(summary.avg_pnl))}
            {stat('Best / Worst /lot', `${money(summary.best_trade)} / ${money(summary.worst_trade)}`)}
            {stat('Avg R', summary.r_tracked_trades ? `${summary.avg_r}R` : '—')}
          </div>
        )}
        {summary?.stats_basis === 'per_standard_lot' && (
          <p className="text-[11px] text-muted-foreground -mt-1">
            Avg / Best / Worst are per your standard lot (set in Settings); Net P&L is actual money.
          </p>
        )}

        {/* Trades table */}
        {trades.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            No journaled trades yet. Closed MT5 trades are recorded here automatically.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  {['Symbol', 'Dir', 'Lots', 'Open', 'Close', 'P&L', 'P&L/lot', 'R', 'Closed'].map((h, i, arr) => (
                    <th key={h} className={`p-2 ${i < 2 || i === arr.length - 1 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => {
                  const pos = (t.profit ?? 0) >= 0
                  return [
                    <tr key={t.id} className="border-b border-border/50 hover:bg-muted/30 cursor-pointer"
                        onClick={() => setExpanded(expanded === t.id ? null : t.id)}>
                      <td className="p-2 font-medium">{t.symbol}</td>
                      <td className="p-2"><span className={t.direction === 'long' ? 'text-emerald-400' : 'text-red-400'}>{(t.direction || t.side || '-').toUpperCase()}</span></td>
                      <td className="p-2 text-right font-mono">{t.lot_size}</td>
                      <td className="p-2 text-right font-mono">{t.open_price}</td>
                      <td className="p-2 text-right font-mono">{t.close_price}</td>
                      <td className={`p-2 text-right font-mono font-semibold ${pos ? 'text-emerald-400' : 'text-red-400'}`}>{money(t.profit ?? 0)}</td>
                      <td className={`p-2 text-right font-mono ${(t.profit_norm ?? t.profit ?? 0) >= 0 ? 'text-emerald-400/80' : 'text-red-400/80'}`}>{money(t.profit_norm ?? t.profit ?? 0)}</td>
                      <td className="p-2 text-right font-mono">
                        {t.r != null ? `${t.r}R` : (
                          <button
                            onClick={(e) => { e.stopPropagation(); fillR(t) }}
                            className="text-[11px] px-1.5 py-0.5 rounded border border-border text-primary hover:bg-primary/10"
                          >set R</button>
                        )}
                      </td>
                      <td className="p-2 text-xs text-muted-foreground">{t.closed_at ? new Date(t.closed_at).toLocaleString() : '-'}</td>
                    </tr>,
                    expanded === t.id && t.note && (
                      <tr key={`${t.id}-note`} className="bg-muted/20">
                        <td colSpan={9} className="p-2 text-xs text-muted-foreground italic">📓 {t.note}</td>
                      </tr>
                    ),
                  ]
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
