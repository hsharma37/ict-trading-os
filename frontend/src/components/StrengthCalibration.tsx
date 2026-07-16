import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { researchApi } from '@/api/client'
import { Gauge, Loader2 } from 'lucide-react'

interface Tier { trades: number; win_rate?: number; expectancy_r?: number; profitable?: boolean; small_sample?: boolean }
interface Calib {
  symbol: string; timeframe: string; target_r: number; breakeven_win_rate: number
  total_trades: number; tiers: Record<string, Tier>; note?: string; error?: string
}

const ORDER = ['STRONG', 'MODERATE', 'WEAK']

export default function StrengthCalibration({ symbol }: { symbol: string }) {
  const [tf, setTf] = useState('1h')
  const [data, setData] = useState<Calib | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null); setData(null)
    try {
      const res = await researchApi.calibrate(symbol, { timeframe: tf, target_r: 3 })
      setData(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Calibration failed')
    } finally { setLoading(false) }
  }, [symbol, tf])

  useEffect(() => { load() }, [load])

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Gauge className="w-4 h-4 text-primary" /> Signal strength — measured
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="ml-auto px-2 py-1 border rounded-md bg-background text-xs">
            <option value="1h">1h</option>
            <option value="1d">1d</option>
          </select>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground mb-2">
          What each ICT-confluence tier actually won historically ({symbol} {tf}, 3R target, net of costs) —
          so “STRONG” means a real number, not a label. Break-even ≈ {data?.breakeven_win_rate ?? 25}% (frictionless);
          the honest test is <strong>expectancy &gt; 0</strong>.
        </p>
        {loading && <p className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> measuring…</p>}
        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}
        {data && !error && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground border-b border-border">
                {['Tier', 'Trades', 'Win rate', 'Expectancy', 'Verdict'].map((h, i) => (
                  <th key={h} className={`p-1.5 ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ORDER.map((name) => {
                const t = data.tiers[name] || { trades: 0 }
                const prof = t.profitable
                return (
                  <tr key={name} className="border-b border-border/40">
                    <td className="p-1.5 font-semibold">{name}</td>
                    <td className="p-1.5 text-right font-mono">{t.trades || '—'}</td>
                    <td className="p-1.5 text-right font-mono">{t.trades ? `${t.win_rate}%` : '—'}</td>
                    <td className={`p-1.5 text-right font-mono ${!t.trades ? '' : (t.expectancy_r ?? 0) > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {t.trades ? `${(t.expectancy_r ?? 0) >= 0 ? '+' : ''}${t.expectancy_r}R` : '—'}
                    </td>
                    <td className="p-1.5 text-right">
                      {!t.trades ? <span className="text-muted-foreground text-xs">no data</span>
                        : prof ? <span className="text-emerald-400 text-xs">profitable{t.small_sample ? ' *' : ''}</span>
                          : <span className="text-red-400 text-xs">loses{t.small_sample ? ' *' : ''}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        {data && data.tiers && Object.values(data.tiers).some((t) => t.small_sample) && (
          <p className="text-[11px] text-muted-foreground mt-1">* small sample (&lt;30 trades) — indicative only.</p>
        )}
      </CardContent>
    </Card>
  )
}
