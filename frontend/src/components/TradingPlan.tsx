import { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { researchApi } from '@/api/client'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { Compass, Loader2, ShieldAlert, Target } from 'lucide-react'

const TIMEFRAMES = ['5m', '15m', '30m', '1h', '4h', '1d']

const regimeTone = (r: string) =>
  r === 'trending_up' ? 'bg-emerald-500/15 text-emerald-400'
    : r === 'trending_down' ? 'bg-red-500/15 text-red-400'
      : r === 'ranging' ? 'bg-sky-500/15 text-sky-400'
        : 'bg-muted text-muted-foreground'

export default function TradingPlan({ defaultSymbol }: { defaultSymbol?: string }) {
  const [sym, setSym] = useState(defaultSymbol || 'EURUSD')
  const [tf, setTf] = useState('1h')
  const [targetR, setTargetR] = useState(2)
  const [plan, setPlan] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const build = useCallback(async () => {
    setLoading(true); setError(null); setPlan(null)
    try {
      const res = await researchApi.plan(sym, { timeframe: tf, target_r: targetR })
      setPlan(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not build a plan')
    } finally { setLoading(false) }
  }, [sym, tf, targetR])

  const rec = plan?.recommendation
  const setup = plan?.setup
  const regime = plan?.regime

  return (
    <Card className="border-primary/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Compass className="w-5 h-5 text-primary" /> Trading Strategist — plan my trading
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Detects the current <strong>regime</strong> on your broker's candles, then recommends only a strategy whose
          style fits it <strong>and</strong> whose after-cost expectancy measured positive on these exact candles —
          otherwise it tells you to stand aside. Execution stays in your hands.
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
          <Button size="sm" onClick={build} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Compass className="w-4 h-4 mr-1" />}
            Plan my trading
          </Button>
        </div>

        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

        {plan && regime && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className={`px-2 py-0.5 rounded-full font-bold uppercase ${regimeTone(regime.regime)}`}>
              {regime.regime.replace('_', ' ')}
            </span>
            <span className="px-2 py-0.5 rounded bg-muted font-mono">ADX {regime.adx}</span>
            <span className="px-2 py-0.5 rounded bg-muted font-mono">ER {regime.efficiency_ratio}</span>
            <span className="px-2 py-0.5 rounded bg-muted font-mono">vol {regime.volatility} ({regime.atr_percentile}%)</span>
            <span className="text-muted-foreground" title={regime.rules}>ⓘ rules</span>
          </div>
        )}

        {plan && plan.action === 'STAND_ASIDE' && (
          <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 text-sm space-y-1">
            <div className="font-semibold text-amber-400 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4" /> Stand aside — no evidence-backed trade here
            </div>
            <p className="text-xs text-muted-foreground">{plan.reason}</p>
          </div>
        )}

        {plan && plan.action === 'TRADE_CANDIDATE' && rec && (
          <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 text-sm space-y-2">
            <div className="font-semibold text-emerald-400 flex items-center gap-2">
              <Target className="w-4 h-4" /> Trade candidate: {rec.label}
            </div>
            <p className="text-xs">{rec.why}</p>

            {setup && (
              <div className={`p-2.5 rounded-md border text-xs space-y-1 ${
                setup.status === 'actionable' ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-border bg-muted/30'}`}>
                {setup.direction ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono">
                    <div><span className="text-muted-foreground">Dir </span><span className={setup.direction === 'LONG' ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>{setup.direction}</span></div>
                    <div><span className="text-muted-foreground">Entry </span>{setup.entry}</div>
                    <div><span className="text-muted-foreground">SL </span>{setup.stop_loss}</div>
                    <div><span className="text-muted-foreground">TP </span>{setup.take_profit}</div>
                  </div>
                ) : null}
                <p className="text-muted-foreground">{setup.note}</p>
              </div>
            )}

            {plan.alternatives?.length > 0 && (
              <p className="text-[11px] text-muted-foreground">
                Also qualified: {plan.alternatives.map((a: any) => `${a.label} (+${a.expectancy_r}R, ${a.trades} trades)`).join(' · ')}
              </p>
            )}
            <p className="text-[11px] text-muted-foreground">{plan.risk_guidance}</p>
          </div>
        )}

        {plan?.caveats && (
          <ul className="text-[11px] text-muted-foreground list-disc pl-4 space-y-0.5">
            {plan.caveats.map((c: string, i: number) => <li key={i}>{c}</li>)}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
