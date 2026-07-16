import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { forwardTestApi } from '@/api/client'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { Radio, Play, Square, Trash2, Loader2, RefreshCw } from 'lucide-react'

interface FwdTest {
  id: string; label: string; symbol: string; timeframe: string; target_r: number
  session_filter: boolean; trend_filter: boolean; started_at: string; status: string
  start_candle_time?: number
  summary?: { trades?: number; win_rate?: number; expectancy_r?: number; total_r?: number }
  open_trade?: { dir: string; entry: number; unrealized_r: number } | null
}

const fmtDate = (s?: string) => (s ? new Date(s).toLocaleDateString() : '—')

export default function ForwardTests({ defaultSymbol }: { defaultSymbol?: string }) {
  const [tests, setTests] = useState<FwdTest[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sym, setSym] = useState(defaultSymbol || 'XAUUSD')
  const [timeframe, setTimeframe] = useState('1d')
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

  const create = async () => {
    setCreating(true); setError(null)
    try {
      await forwardTestApi.create({ symbol: sym, timeframe, target_r: targetR, session_filter: killzone, trend_filter: trend })
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
          Lock a config and track it against candles printed <strong>from now on</strong> — true forward, un-fittable
          out-of-sample. No orders placed; trades accrue as new bars close (updates each hour on the 1h chart).
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
            <span className="text-muted-foreground">TF</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="1d">1d</option>
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
                      <span className="font-bold">{t.symbol}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-muted font-mono">{t.target_r}R{t.session_filter ? ' · KZ' : ''}{t.trend_filter ? ' · trend' : ''}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${t.status === 'running' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'}`}>{t.status}</span>
                      <span className="text-xs text-muted-foreground">since {fmtDate(t.started_at)}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
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
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
