import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { researchApi } from '@/api/client'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { FlaskConical, Brain, Loader2, Trophy } from 'lucide-react'

interface StratMeta { key: string; label: string; style: string; source: string }
interface CompareRow {
  strategy: string; label: string; style: string; trades: number
  win_rate?: number; expectancy_r?: number; total_r?: number; max_drawdown_r?: number
}

const TIMEFRAMES = ['5m', '15m', '30m', '1h', '4h', '1d']

export default function StrategyLab({ defaultSymbol }: { defaultSymbol?: string }) {
  const [strategies, setStrategies] = useState<StratMeta[]>([])
  const [sym, setSym] = useState(defaultSymbol || 'EURUSD')
  const [tf, setTf] = useState('1h')
  const [targetR, setTargetR] = useState(2)
  const [compare, setCompare] = useState<{ strategies: CompareRow[]; note?: string; candles?: number } | null>(null)
  const [comparing, setComparing] = useState(false)
  const [ml, setMl] = useState<any>(null)
  const [mlLoading, setMlLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    researchApi.strategies().then((r) => setStrategies(r.data?.strategies || [])).catch(() => {})
  }, [])

  const runCompare = useCallback(async () => {
    setComparing(true); setError(null); setCompare(null)
    try {
      const res = await researchApi.strategyCompare(sym, { timeframe: tf, target_r: targetR, history_range: '1y' })
      setCompare(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Strategy comparison failed')
    } finally { setComparing(false) }
  }, [sym, tf, targetR])

  const runMl = useCallback(async () => {
    setMlLoading(true); setError(null); setMl(null)
    try {
      const res = await researchApi.mlBaseline(sym, { timeframe: tf, history_range: '1y' })
      setMl(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'ML baseline failed')
    } finally { setMlLoading(false) }
  }, [sym, tf])

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-primary" /> Strategy Lab — classic quant strategies, one honest referee
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Six well-documented open-source strategies (trend, mean-reversion, breakout) plus the ICT confluence
          baseline — all backtested on the <strong>same broker candles</strong>, net of estimated costs, 1.5×ATR stop,
          one trade at a time. Ranked by after-cost expectancy: <strong>&gt; 0R is the bar</strong>.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Symbol</span>
            <select value={sym} onChange={(e) => setSym(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm font-semibold">
              {SUPPORTED_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">TF</span>
            <select value={tf} onChange={(e) => setTf(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              {TIMEFRAMES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Target</span>
            <select value={targetR} onChange={(e) => setTargetR(Number(e.target.value))} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              {[1.5, 2, 3].map((r) => <option key={r} value={r}>{r}R</option>)}
            </select>
          </label>
          <Button size="sm" onClick={runCompare} disabled={comparing}>
            {comparing ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Trophy className="w-4 h-4 mr-1" />}
            Compare all strategies
          </Button>
          <Button size="sm" variant="outline" onClick={runMl} disabled={mlLoading}
            title="Walk-forward logistic regression: can price features predict the next bar out of sample?">
            {mlLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Brain className="w-4 h-4 mr-1" />}
            ML baseline
          </Button>
        </div>

        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

        {compare && compare.strategies && (
          <div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground border-b border-border">
                  {['Strategy', 'Style', 'Trades', 'Win rate', 'Expectancy', 'Total', 'Max DD'].map((h, i) => (
                    <th key={h} className={`p-1.5 ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compare.strategies.map((r) => {
                  const exp = r.expectancy_r ?? 0
                  return (
                    <tr key={r.strategy} className={`border-b border-border/40 ${r.strategy === 'ict_confluence' ? 'bg-muted/30' : ''}`}>
                      <td className="p-1.5 font-semibold">{r.label}</td>
                      <td className="p-1.5 text-right text-xs text-muted-foreground">{r.style}</td>
                      <td className="p-1.5 text-right font-mono">{r.trades || '—'}</td>
                      <td className="p-1.5 text-right font-mono">{r.trades ? `${r.win_rate}%` : '—'}</td>
                      <td className={`p-1.5 text-right font-mono ${!r.trades ? '' : exp > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {r.trades ? `${exp >= 0 ? '+' : ''}${exp}R` : '—'}
                      </td>
                      <td className="p-1.5 text-right font-mono">{r.trades ? `${(r.total_r ?? 0) >= 0 ? '+' : ''}${r.total_r}R` : '—'}</td>
                      <td className="p-1.5 text-right font-mono">{r.trades ? `${r.max_drawdown_r}R` : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {compare.note && <p className="text-[11px] text-muted-foreground mt-1.5">{compare.note}</p>}
          </div>
        )}

        {ml && (
          <div className={`p-3 rounded-lg border text-sm space-y-1.5 ${
            ml.tone === 'good' ? 'border-emerald-500/30 bg-emerald-500/5'
              : ml.tone === 'warn' ? 'border-amber-500/30 bg-amber-500/5'
                : 'border-border bg-muted/20'}`}>
            <div className="font-semibold flex items-center gap-2">
              <Brain className="w-4 h-4" /> ML baseline — {ml.symbol} {ml.timeframe}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">OOS accuracy</div><div className="font-bold font-mono">{ml.oos_accuracy_pct}%</div></div>
              <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Majority baseline</div><div className="font-bold font-mono">{ml.majority_baseline_pct}%</div></div>
              <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">Edge</div><div className={`font-bold font-mono ${ml.edge_pp > 1 ? 'text-emerald-400' : ''}`}>{ml.edge_pp >= 0 ? '+' : ''}{ml.edge_pp}pp</div></div>
              <div className="p-2 rounded bg-muted"><div className="text-muted-foreground">OOS predictions</div><div className="font-bold font-mono">{ml.oos_predictions}</div></div>
            </div>
            <p className="text-xs">{ml.verdict}</p>
            <p className="text-[11px] text-muted-foreground">{ml.model} · {ml.method}</p>
            <p className="text-[11px] text-muted-foreground">{ml.caveat}</p>
          </div>
        )}

        {strategies.length > 0 && !compare && (
          <div className="text-[11px] text-muted-foreground space-y-0.5">
            {strategies.map((s) => (
              <div key={s.key}><span className="font-semibold text-foreground/80">{s.label}</span> — {s.source}</div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
