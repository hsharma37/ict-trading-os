import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { researchApi } from '@/api/client'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { FlaskConical, Dice5, Loader2, AlertTriangle } from 'lucide-react'

function Sparkline({ data, color = 'currentColor' }: { data: number[]; color?: string }) {
  if (!data || data.length < 2) return null
  const w = 480, h = 90
  const min = Math.min(...data), max = Math.max(...data)
  const span = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / span) * h}`).join(' ')
  const zeroY = h - ((0 - min) / span) * h
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-20" preserveAspectRatio="none">
      {min < 0 && max > 0 && <line x1="0" y1={zeroY} x2={w} y2={zeroY} stroke="currentColor" strokeOpacity="0.2" strokeDasharray="4" />}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

const Stat = ({ label, value, cls = '' }: { label: string; value: string; cls?: string }) => (
  <div className="p-2.5 rounded-lg bg-muted">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className={`text-base font-bold font-mono ${cls}`}>{value}</div>
  </div>
)

// Translate the raw stats into plain English + money, not just ratios.
function explainBacktest(bt: any): { tone: 'good' | 'bad' | 'warn'; lines: string[] } {
  const be = +(100 / (1 + bt.target_r)).toFixed(1)          // break-even win rate at this R:R
  const expPer100 = Math.round(bt.expectancy_r * 100)        // $ per $100 risked, per trade
  const totalPer100 = Math.round(bt.total_r * 100)           // cumulative on $100/trade risk
  const tone = bt.expectancy_r > 0.05 ? 'good' : bt.expectancy_r < -0.05 ? 'bad' : 'warn'
  const lines: string[] = []
  lines.push(
    `At a ${bt.target_r}:1 target you must win ${be}% of trades just to break even. This setup won ${bt.win_rate}% — ${bt.win_rate >= be ? 'above' : 'below'} the line.`
  )
  lines.push(
    expPer100 === 0
      ? `Average edge ≈ $0 per trade: for every $100 you risk you get about $100 back — a coin flip after the effort.`
      : `On average each trade ${expPer100 >= 0 ? 'makes' : 'loses'} $${Math.abs(expPer100)} for every $100 risked. Across the ${bt.trades} trades that compounded to ${totalPer100 >= 0 ? '+' : '−'}$${Math.abs(totalPer100)} per $100-risk unit.`
  )
  lines.push(
    `Brace for the ride: the worst run was ${bt.max_loss_streak} losses in a row and a ${bt.max_drawdown_r}R drawdown${bt.profit_factor != null ? `. You earned $${bt.profit_factor} for every $1 you lost.` : '.'}`
  )
  if (tone === 'bad') lines.push('Bottom line: repeated at size this bleeds money — the ~1-in-3 wins aren\'t frequent or big enough to cover the losses. Don\'t trade it as-is.')
  else if (tone === 'warn') lines.push('Bottom line: no real edge — it\'s roughly break-even before spread/commission, which would tip it negative. Not tradeable for profit yet.')
  else lines.push('Bottom line: a positive expectancy here — but confirm it survives spread/commission and out-of-sample data before trusting it.')
  return { tone, lines }
}

function explainMonteCarlo(mc: any): string[] {
  const f = mc.final_return_pct
  const lines: string[] = []
  lines.push(
    `Same edge, ${mc.n_sims.toLocaleString()} alternate histories (only luck differs): the typical outcome was ${f.median >= 0 ? '+' : ''}${f.median}%, but results ranged from ${f.p5}% (unlucky) to ${f.p95}% (lucky). Order of wins/losses alone causes that spread.`
  )
  lines.push(
    `${mc.prob_loss_pct}% of those histories ended down money${mc.prob_loss_pct >= 50 ? ' — you\'re more likely to lose than win' : ''}. Deepest drawdown was typically ${mc.max_drawdown_pct.median}%, and a rough ${mc.max_drawdown_pct.p95}% in the worst 1-in-20.`
  )
  lines.push(
    mc.risk_of_ruin_pct > 10
      ? `Risk of ruin ${mc.risk_of_ruin_pct}%: that often your account fell ${mc.ruin_drawdown_pct}% — unacceptable; cut risk-per-trade or don\'t trade this.`
      : `Risk of ruin ${mc.risk_of_ruin_pct}% at ${mc.risk_per_trade_pct}% risk/trade — the sizing itself won\'t blow you up, though the edge still has to be real.`
  )
  return lines
}

export default function BacktestPanel({ symbol: initialSymbol }: { symbol?: string }) {
  const [symbol, setSymbol] = useState(initialSymbol || SUPPORTED_SYMBOLS[0] || 'EURUSD')
  const [targetR, setTargetR] = useState(2)
  const [timeframe, setTimeframe] = useState('1h')
  const [bt, setBt] = useState<any>(null)
  const [mc, setMc] = useState<any>(null)
  const [riskPct, setRiskPct] = useState(1)
  const [loading, setLoading] = useState(false)
  const [mcLoading, setMcLoading] = useState(false)
  const [sweep, setSweep] = useState<any>(null)
  const [sweepLoading, setSweepLoading] = useState(false)
  const [honest, setHonest] = useState<any>(null)
  const [honestLoading, setHonestLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Follow the page's selected instrument when it changes, but stay usable on
  // its own (the panel has its own picker, so it's always visible).
  useEffect(() => { if (initialSymbol) setSymbol(initialSymbol) }, [initialSymbol])

  const runSweep = async () => {
    setSweepLoading(true); setError(null); setSweep(null)
    try {
      const res = await researchApi.sweep(symbol, { timeframe, history_range: '1y' })
      setSweep(res.data)
    } catch (e: any) {
      setSweep(null); setError(e?.response?.data?.detail || 'Sweep failed')
    } finally { setSweepLoading(false) }
  }

  const runHonest = async () => {
    setHonestLoading(true); setError(null); setHonest(null)
    try {
      const res = await researchApi.honestTest(symbol, { timeframe, history_range: '1y' })
      setHonest(res.data)
    } catch (e: any) {
      setHonest(null); setError(e?.response?.data?.detail || 'Honest test failed')
    } finally { setHonestLoading(false) }
  }

  const runBacktest = async () => {
    setLoading(true); setError(null); setMc(null); setBt(null)
    try {
      const res = await researchApi.backtest(symbol, { timeframe, target_r: targetR, history_range: '1y' })
      setBt(res.data)
    } catch (e: any) {
      setBt(null); setError(e?.response?.data?.detail || 'Backtest failed')
    } finally { setLoading(false) }
  }

  const runMonteCarlo = async () => {
    if (!bt?.r_values?.length) return
    setMcLoading(true); setError(null)
    try {
      const res = await researchApi.monteCarlo({ r_values: bt.r_values, n_sims: 2000, risk_per_trade_pct: riskPct })
      setMc(res.data)
    } catch (e: any) {
      setMc(null); setError(e?.response?.data?.detail || 'Monte Carlo failed')
    } finally { setMcLoading(false) }
  }

  const edge = bt && bt.trades > 0
    ? (bt.expectancy_r > 0.05 ? { t: 'Positive edge', c: 'text-emerald-400' }
      : bt.expectancy_r < -0.05 ? { t: 'Negative edge (loses money)', c: 'text-red-400' }
        : { t: 'No demonstrated edge (≈ break-even)', c: 'text-amber-400' })
    : null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-primary" /> Backtest & Monte Carlo
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Walk-forward replay of the ICT signal over ~1y of candles (no look-ahead). Then Monte Carlo
          re-samples the resulting trades to show the range of outcomes luck can produce from the same edge.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Symbol</span>
            <select value={symbol} onChange={(e) => { setSymbol(e.target.value); setBt(null); setMc(null) }}
              className="px-2 py-1.5 border rounded-md bg-background text-sm font-semibold">
              {SUPPORTED_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">TF</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="px-2 py-1.5 border rounded-md bg-background text-sm">
              <option value="1h">1h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Target</span>
            <input type="number" step="0.5" min="0.5" max="5" value={targetR}
              onChange={(e) => setTargetR(parseFloat(e.target.value) || 2)}
              className="w-16 px-2 py-1.5 border rounded-md bg-background text-sm" /> R
          </label>
          <Button size="sm" onClick={runBacktest} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <FlaskConical className="w-4 h-4 mr-1" />}
            Run backtest
          </Button>
          <Button size="sm" variant="outline" onClick={runSweep} disabled={sweepLoading} title="Grid-search target-R × session × trend to find if any config has an edge">
            {sweepLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <FlaskConical className="w-4 h-4 mr-1" />}
            Find best config
          </Button>
          <Button size="sm" variant="outline" onClick={runHonest} disabled={honestLoading}
            title="Pick the best config on the first 60% of history, lock it, and report ONLY the untouched last 40% — the real anti-curve-fit test">
            {honestLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Dice5 className="w-4 h-4 mr-1" />}
            Honest test
          </Button>
        </div>

        {/* Honest walk-forward test */}
        {honest && honest.verdict && (
          <div className={`p-3 rounded-lg border text-sm space-y-2 ${
            honest.verdict.tone === 'good' ? 'border-emerald-500/30 bg-emerald-500/5'
              : honest.verdict.tone === 'warn' ? 'border-amber-500/30 bg-amber-500/5'
                : 'border-red-500/30 bg-red-500/5'}`}>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Honest walk-forward test — trained on first {honest.train_split_pct}%, tested on the rest
            </div>
            <p className="leading-relaxed">{honest.verdict.text}</p>
            {honest.chosen_config && honest.test?.trades > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                <Stat label="Chosen (blind)" value={`${honest.chosen_config.target_r}R${honest.chosen_config.session_filter ? ' · KZ' : ''}${honest.chosen_config.trend_filter ? ' · trend' : ''}`} />
                <Stat label="Train exp." value={`${honest.chosen_config.train_expectancy_r >= 0 ? '+' : ''}${honest.chosen_config.train_expectancy_r}R`} />
                <Stat label="Test trades" value={`${honest.test.trades} · ${honest.test.win_rate}%`} />
                <Stat label="Test exp. (unseen)" value={`${honest.test.expectancy_r >= 0 ? '+' : ''}${honest.test.expectancy_r}R`}
                  cls={honest.test.expectancy_r > 0.05 ? 'text-emerald-400' : honest.test.expectancy_r < -0.02 ? 'text-red-400' : 'text-amber-400'} />
              </div>
            )}
          </div>
        )}

        {/* Parameter sweep results */}
        {sweep && sweep.verdict && (
          <div className="space-y-2">
            <div className={`p-3 rounded-lg border text-sm ${
              sweep.verdict.tone === 'good' ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200'
                : sweep.verdict.tone === 'warn' ? 'border-amber-500/30 bg-amber-500/5 text-amber-200'
                  : 'border-red-500/30 bg-red-500/5 text-red-200'}`}>
              <div className="text-xs font-semibold uppercase tracking-wide mb-1 opacity-80">Parameter sweep — {sweep.configs_tested} configs, OOS split {sweep.oos_split_pct}%</div>
              {sweep.verdict.text}
            </div>
            {sweep.configs?.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      {['Target', 'Filters', 'Trades', 'Win%', 'Exp', 'In-samp', 'Out-samp', 'Ruin%'].map((h, i) => (
                        <th key={h} className={`p-1.5 ${i < 2 ? 'text-left' : 'text-right'}`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sweep.configs.slice(0, 6).map((c: any, idx: number) => (
                      <tr key={idx} className={`border-b border-border/50 ${idx === 0 ? 'bg-emerald-500/5' : ''}`}>
                        <td className="p-1.5 font-mono">{c.target_r}R</td>
                        <td className="p-1.5">{[c.session_filter && 'killzone', c.trend_filter && 'trend'].filter(Boolean).join(' + ') || 'none'}</td>
                        <td className="p-1.5 text-right font-mono">{c.trades}</td>
                        <td className="p-1.5 text-right font-mono">{c.win_rate}%</td>
                        <td className={`p-1.5 text-right font-mono font-semibold ${c.expectancy_r > 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.expectancy_r >= 0 ? '+' : ''}{c.expectancy_r}R</td>
                        <td className="p-1.5 text-right font-mono text-muted-foreground">{c.is_expectancy_r ?? '—'}</td>
                        <td className={`p-1.5 text-right font-mono ${c.oos_expectancy_r > 0 ? 'text-emerald-400' : c.oos_expectancy_r < 0 ? 'text-red-400' : ''}`}>{c.oos_expectancy_r ?? '—'}</td>
                        <td className="p-1.5 text-right font-mono">{c.risk_of_ruin_pct ?? '—'}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Top 6 by expectancy. <strong>Out-samp</strong> = expectancy on the last {100 - sweep.oos_split_pct}% of data the config wasn't chosen on — if it stays positive there, the edge is more likely real than curve-fit.
                </p>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}

        {bt && bt.trades === 0 && (
          <p className="text-sm text-muted-foreground">{bt.note || 'No qualifying signals fired over this window.'}</p>
        )}

        {bt && bt.trades > 0 && (
          <div className="space-y-3">
            {edge && <div className={`text-sm font-semibold ${edge.c}`}>{edge.t}</div>}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Stat label="Trades" value={String(bt.trades)} />
              <Stat label="Win rate" value={`${bt.win_rate}%`} />
              <Stat label="Expectancy" value={`${bt.expectancy_r >= 0 ? '+' : ''}${bt.expectancy_r}R`} cls={bt.expectancy_r >= 0 ? 'text-emerald-400' : 'text-red-400'} />
              <Stat label="Profit factor" value={bt.profit_factor != null ? String(bt.profit_factor) : '—'} />
              <Stat label="Total" value={`${bt.total_r >= 0 ? '+' : ''}${bt.total_r}R`} />
              <Stat label="Max DD" value={`${bt.max_drawdown_r}R`} cls="text-red-400" />
              <Stat label="Worst streak" value={`${bt.max_loss_streak} losses`} />
              <Stat label="Avg win / loss" value={`${bt.avg_win_r} / ${bt.avg_loss_r}R`} />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Equity curve (cumulative R)</div>
              <div className={bt.total_r >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                <Sparkline data={bt.equity_curve_r} />
              </div>
            </div>
            {/* Plain-English interpretation */}
            {(() => {
              const ex = explainBacktest(bt)
              const box = ex.tone === 'good' ? 'border-emerald-500/30 bg-emerald-500/5'
                : ex.tone === 'bad' ? 'border-red-500/30 bg-red-500/5' : 'border-amber-500/30 bg-amber-500/5'
              return (
                <div className={`p-3 rounded-lg border ${box} space-y-1.5`}>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">What this means</div>
                  {ex.lines.map((l, i) => <p key={i} className="text-sm leading-relaxed">{l}</p>)}
                </div>
              )
            })()}
            <p className="text-[11px] text-muted-foreground">
              {bt.sample_caveat ? `⚠ ${bt.sample_caveat} ` : ''}Assumptions: {bt.assumptions}
            </p>

            {/* Monte Carlo */}
            <div className="pt-2 border-t border-border">
              <div className="flex flex-wrap items-center gap-3 mb-2">
                <span className="text-sm font-semibold flex items-center gap-1.5"><Dice5 className="w-4 h-4" /> Monte Carlo</span>
                <label className="flex items-center gap-1.5 text-sm">
                  <span className="text-muted-foreground">Risk/trade</span>
                  <input type="number" step="0.25" min="0.25" max="5" value={riskPct}
                    onChange={(e) => setRiskPct(parseFloat(e.target.value) || 1)}
                    className="w-16 px-2 py-1.5 border rounded-md bg-background text-sm" /> %
                </label>
                <Button size="sm" variant="outline" onClick={runMonteCarlo} disabled={mcLoading}>
                  {mcLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Dice5 className="w-4 h-4 mr-1" />}
                  Run 2,000 simulations
                </Button>
              </div>

              {mc && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    <Stat label="Median return" value={`${mc.final_return_pct.median >= 0 ? '+' : ''}${mc.final_return_pct.median}%`} cls={mc.final_return_pct.median >= 0 ? 'text-emerald-400' : 'text-red-400'} />
                    <Stat label="Range (p5→p95)" value={`${mc.final_return_pct.p5}% → ${mc.final_return_pct.p95}%`} />
                    <Stat label="Prob. of loss" value={`${mc.prob_loss_pct}%`} cls={mc.prob_loss_pct > 50 ? 'text-red-400' : ''} />
                    <Stat label="Median max DD" value={`${mc.max_drawdown_pct.median}%`} />
                    <Stat label="Worst-case DD (p95)" value={`${mc.max_drawdown_pct.p95}%`} cls="text-red-400" />
                    <Stat label={`Risk of ruin (−${mc.ruin_drawdown_pct}%)`} value={`${mc.risk_of_ruin_pct}%`} cls={mc.risk_of_ruin_pct > 10 ? 'text-red-400' : 'text-emerald-400'} />
                  </div>
                  <div className="p-3 rounded-lg border border-border bg-muted/30 space-y-1.5">
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">What this means</div>
                    {explainMonteCarlo(mc).map((l, i) => <p key={i} className="text-sm leading-relaxed">{l}</p>)}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {mc.n_sims.toLocaleString()} simulations of {mc.horizon} trades, {mc.risk_per_trade_pct}% risk each, compounding from ${mc.start_equity.toLocaleString()}. Source: {mc.origin}.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
