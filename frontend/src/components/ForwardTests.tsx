import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { forwardTestApi, researchApi } from '@/api/client'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { Radio, Play, Square, Trash2, Loader2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'

interface FwdTrade {
  r: number; dir: string; entry: number; sl?: number; target?: number
  outcome?: string; entry_time?: number; exit_time?: number
}
interface FwdTest {
  id: string; label: string; symbol: string; timeframe: string; target_r: number
  strategy?: string; min_confluence?: number; last_checked?: string
  session_filter: boolean; trend_filter: boolean; started_at: string; status: string
  start_candle_time?: number
  trades?: FwdTrade[]
  summary?: { trades?: number; win_rate?: number; expectancy_r?: number; total_r?: number }
  open_trade?: { dir: string; entry: number; sl?: number; target?: number; unrealized_r: number; entry_time?: number } | null
}

const fmtDate = (s?: string) => (s ? new Date(s).toLocaleDateString() : '—')
const fmtBar = (t?: number) => (t ? new Date(t * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—')
const ago = (s?: string) => {
  if (!s) return '—'
  const m = Math.max(0, Math.round((Date.now() - new Date(s).getTime()) / 60000))
  return m < 1 ? 'just now' : m < 60 ? `${m}m ago` : `${Math.round(m / 60)}h ago`
}
const outcomeBadge = (o?: string) =>
  o === 'target' ? 'bg-emerald-500/15 text-emerald-400'
    : o === 'stop' ? 'bg-red-500/15 text-red-400'
      : 'bg-muted text-muted-foreground'

export default function ForwardTests({ defaultSymbol }: { defaultSymbol?: string }) {
  const [tests, setTests] = useState<FwdTest[]>([])
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sym, setSym] = useState(defaultSymbol || 'GBPUSD')
  const [strategy, setStrategy] = useState('ict_confluence')
  const [strategies, setStrategies] = useState<{ key: string; label: string }[]>([])
  const [name, setName] = useState('')
  const [tf, setTf] = useState('1h')
  const [targetR, setTargetR] = useState(3)
  const [killzone, setKillzone] = useState(false)
  const [trend, setTrend] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await forwardTestApi.list()
      setTests(res.data?.forward_tests || [])
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load forward tests')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    researchApi.strategies().then((r) => setStrategies(r.data?.strategies || [])).catch(() => {})
  }, [])

  const create = async () => {
    setCreating(true); setError(null)
    try {
      await forwardTestApi.create({ symbol: sym, timeframe: tf, target_r: targetR, session_filter: killzone, trend_filter: trend, name: name.trim(), strategy })
      setName('')
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not start forward test')
    } finally { setCreating(false) }
  }

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); await load() } catch (e: any) { setError(e?.response?.data?.detail || 'Action failed') }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Radio className="w-5 h-5 text-primary" /> Live Paper-Forward Test
        </CardTitle>
        <button onClick={load} className="text-muted-foreground hover:text-foreground">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Lock a config, give it a name, and track it against candles printed <strong>from now on</strong> — true forward,
          un-fittable out-of-sample. No orders placed. The list loads stored stats instantly; hit a test's refresh
          button to recompute it from the latest candles.
        </p>

        {/* Start a new forward test */}
        <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-border bg-muted/20">
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Symbol</span>
            <select value={sym} onChange={(e) => setSym(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm font-semibold">
              {SUPPORTED_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Strategy</span>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              <option value="ict_confluence">ICT confluence</option>
              {strategies.map((st) => <option key={st.key} value={st.key}>{st.label}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Name</span>
            <input type="text" value={name} placeholder="e.g. GU trend 3R"
              onChange={(e) => setName(e.target.value)} maxLength={40}
              className="w-36 px-2 py-1.5 border rounded-md bg-background text-sm" />
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">TF</span>
            <select value={tf} onChange={(e) => setTf(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              {['5m', '15m', '30m', '1h', '4h', '1d'].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Target</span>
            <input type="number" step="0.5" min="0.5" max="5" value={targetR}
              onChange={(e) => setTargetR(parseFloat(e.target.value) || 3)}
              className="w-16 px-2 py-1.5 border rounded-md bg-background text-sm" /> R
          </label>
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" checked={killzone} onChange={(e) => setKillzone(e.target.checked)} /> Killzone-only
          </label>
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" checked={trend} onChange={(e) => setTrend(e.target.checked)} /> Trend-aligned
          </label>
          <Button size="sm" onClick={create} disabled={creating}>
            {creating ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Play className="w-4 h-4 mr-1" />}
            Start forward test
          </Button>
        </div>

        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

        {tests.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-3">No forward tests yet. Start one above to validate a config on future data.</p>
        ) : (
          <div className="space-y-2">
            {tests.map((t) => {
              const s = t.summary || {}
              const exp = s.expectancy_r ?? 0
              const n = s.trades ?? 0
              return (
                <div key={t.id} className="p-3 rounded-lg border border-border bg-card">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold">{t.label || t.symbol}</span>
                      <span className="text-xs text-muted-foreground">{t.symbol}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-muted font-mono">{t.strategy && t.strategy !== 'ict_confluence' ? `${t.strategy} · ` : 'ICT · '}{t.timeframe} · {t.target_r}R{t.session_filter ? ' · KZ' : ''}{t.trend_filter ? ' · trend' : ''}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${t.status === 'running' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'}`}>{t.status}</span>
                      <span className="text-xs text-muted-foreground">since {fmtDate(t.started_at)}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => setExpanded((e) => ({ ...e, [t.id]: !e[t.id] }))} title="Show details"
                        className="px-1.5 py-0.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground">
                        {expanded[t.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                      {t.status === 'running' && (
                        <button onClick={() => act(() => forwardTestApi.refresh(t.id))} title="Refresh stats from current candles"
                          className="px-1.5 py-0.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground"><RefreshCw className="w-3 h-3" /></button>
                      )}
                      {t.status === 'running' && (
                        <button onClick={() => act(() => forwardTestApi.stop(t.id))} title="Stop"
                          className="px-1.5 py-0.5 rounded border border-border text-xs text-muted-foreground hover:text-amber-400"><Square className="w-3 h-3" /></button>
                      )}
                      <button onClick={() => act(() => forwardTestApi.remove(t.id))} title="Delete"
                        className="px-1.5 py-0.5 rounded border border-border text-xs text-muted-foreground hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-3 md:grid-cols-4 gap-2 text-xs">
                    <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Fwd trades</div><div className="font-bold font-mono">{n}</div></div>
                    <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Win rate</div><div className="font-bold font-mono">{n ? `${s.win_rate}%` : '—'}</div></div>
                    <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Expectancy</div><div className={`font-bold font-mono ${exp > 0 ? 'text-emerald-400' : exp < 0 ? 'text-red-400' : ''}`}>{n ? `${exp >= 0 ? '+' : ''}${exp}R` : '—'}</div></div>
                    <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Total</div><div className="font-bold font-mono">{n ? `${(s.total_r ?? 0) >= 0 ? '+' : ''}${s.total_r}R` : '—'}</div></div>
                  </div>
                  {t.open_trade && (
                    <div className="mt-1.5 text-xs text-muted-foreground">
                      Open: {t.open_trade.dir} @ {t.open_trade.entry} · unrealized {t.open_trade.unrealized_r >= 0 ? '+' : ''}{t.open_trade.unrealized_r}R
                    </div>
                  )}
                  {n === 0 && !t.open_trade && (
                    <div className="mt-1.5 text-[11px] text-muted-foreground">No signals since it started — give it time; trades accrue as new candles print.</div>
                  )}
                  {expanded[t.id] && (
                    <div className="mt-2 pt-2 border-t border-border/50 space-y-2 text-xs">
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                        <span>Started <span className="text-foreground">{fmtDate(t.started_at)}</span></span>
                        <span>Stats updated <span className="text-foreground">{ago(t.last_checked)}</span></span>
                        <span>Config: <span className="text-foreground font-mono">{t.strategy && t.strategy !== 'ict_confluence' ? t.strategy : `ICT ≥${t.min_confluence ?? 2}`} · {t.timeframe} · {t.target_r}R{t.session_filter ? ' · killzone' : ''}{t.trend_filter ? ' · trend' : ''}</span></span>
                      </div>
                      {t.open_trade && (
                        <div className="p-2 rounded bg-emerald-500/5 border border-emerald-500/20 font-mono">
                          OPEN {t.open_trade.dir} @ {t.open_trade.entry} · SL {t.open_trade.sl ?? '—'} · TP {t.open_trade.target ?? '—'} · since {fmtBar(t.open_trade.entry_time)} · {t.open_trade.unrealized_r >= 0 ? '+' : ''}{t.open_trade.unrealized_r}R unrealized
                        </div>
                      )}
                      {(t.trades?.length ?? 0) > 0 ? (
                        <table className="w-full">
                          <thead>
                            <tr className="text-muted-foreground border-b border-border/40">
                              {['Entry time', 'Dir', 'Entry', 'SL', 'TP', 'Outcome', 'R'].map((h, i) => (
                                <th key={h} className={`p-1 ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {[...(t.trades || [])].slice(-12).reverse().map((tr, i) => (
                              <tr key={i} className="border-b border-border/20 font-mono">
                                <td className="p-1 text-left">{fmtBar(tr.entry_time)}</td>
                                <td className={`p-1 text-right ${tr.dir === 'long' || tr.dir === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>{tr.dir}</td>
                                <td className="p-1 text-right">{tr.entry}</td>
                                <td className="p-1 text-right">{tr.sl ?? '—'}</td>
                                <td className="p-1 text-right">{tr.target ?? '—'}</td>
                                <td className="p-1 text-right"><span className={`px-1.5 py-0.5 rounded ${outcomeBadge(tr.outcome)}`}>{tr.outcome ?? '—'}</span></td>
                                <td className={`p-1 text-right ${tr.r > 0 ? 'text-emerald-400' : 'text-red-400'}`}>{tr.r >= 0 ? '+' : ''}{tr.r}R</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="text-muted-foreground">No closed trades yet.</div>
                      )}
                      {(t.trades?.length ?? 0) > 12 && (
                        <div className="text-[11px] text-muted-foreground">Showing the last 12 of {t.trades!.length} trades.</div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
