import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { researchApi } from '@/api/client'
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

export default function BacktestPanel({ symbol }: { symbol: string }) {
  const [targetR, setTargetR] = useState(2)
  const [timeframe, setTimeframe] = useState('1h')
  const [bt, setBt] = useState<any>(null)
  const [mc, setMc] = useState<any>(null)
  const [riskPct, setRiskPct] = useState(1)
  const [loading, setLoading] = useState(false)
  const [mcLoading, setMcLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runBacktest = async () => {
    setLoading(true); setError(null); setMc(null)
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
          <FlaskConical className="w-5 h-5 text-primary" /> Backtest & Monte Carlo — {symbol}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Walk-forward replay of the ICT signal over ~1y of candles (no look-ahead). Then Monte Carlo
          re-samples the resulting trades to show the range of outcomes luck can produce from the same edge.
        </p>

        <div className="flex flex-wrap items-center gap-3">
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
        </div>

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
