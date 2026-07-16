import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { researchApi } from '@/api/client'
import BacktestPanel from '@/components/BacktestPanel'
import {
  Activity, DollarSign, AlertTriangle, Shield, Globe, BarChart3, Layers,
} from 'lucide-react'

interface InstrumentAnalysis {
  symbol: string
  label: string
  kind: string
  current_price: number
  change: number
  change_pct: number
  trend: string
  sentiment: string
  reasoning?: string
  news?: { title: string; impact: string; source: string; link: string }[]
  volatility: { atr: number | null; daily_range: number | null; volatility_pct: number | null }
  support: number | null
  resistance: number | null
  dist_to_support: number | null
  dist_to_resistance: number | null
  key_levels: { level: number; type: string }[]
  sma20: number | null
  sma50: number | null
  data_quality?: 'live' | 'stale' | 'synthetic'
  data_source?: string
  stale?: boolean
  synthetic?: boolean
  timestamp: string
}

function DataQualityBadge({ a }: { a: { data_quality?: string; data_source?: string } }) {
  const q = a.data_quality || 'live'
  if (q === 'synthetic') {
    return <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">⚠ simulated data — not tradeable</span>
  }
  if (q === 'stale') {
    return <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">stale feed</span>
  }
  return <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300/90 border border-emerald-500/20">live · {a.data_source || 'source'}</span>
}

export default function Research() {
  const [instruments, setInstruments] = useState<InstrumentAnalysis[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [correlation, setCorrelation] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [allRes, corrRes] = await Promise.all([
          researchApi.all(),
          researchApi.correlation(),
        ])
        setInstruments(allRes.data?.instruments || [])
        setCorrelation(corrRes.data)
      } catch (err: any) {
        setError(err.message || 'Failed to load research data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const selected = instruments.find(i => i.symbol === selectedSymbol)
  const isPositive = (val: number) => val >= 0

  const kindIcons: Record<string, any> = {
    fx: <DollarSign className="w-4 h-4" />,
    index: <BarChart3 className="w-4 h-4" />,
    metal: <Shield className="w-4 h-4" />,
    crypto: <Globe className="w-4 h-4" />,
    commodity: <Layers className="w-4 h-4" />,
  }

  const kindColors: Record<string, string> = {
    fx: 'text-blue-400',
    index: 'text-blue-400',
    metal: 'text-yellow-400',
    crypto: 'text-purple-400',
    commodity: 'text-orange-400',
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Research</h1>
        <p className="text-muted-foreground">Loading instrument analysis...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Research</h1>
        <p className="text-muted-foreground">Technical analysis and market insights</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Instrument Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {instruments.map((inst) => {
          const positive = isPositive(inst.change_pct)
          return (
            <button
              key={inst.symbol}
              onClick={() => setSelectedSymbol(inst.symbol === selectedSymbol ? null : inst.symbol)}
              className={`p-4 rounded-xl border text-left transition-all hover:scale-[1.02] ${
                selectedSymbol === inst.symbol
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                  : 'border-border bg-card hover:bg-muted/50'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={kindColors[inst.kind] || 'text-muted-foreground'}>
                    {kindIcons[inst.kind] || <Activity className="w-4 h-4" />}
                  </span>
                  <span className="font-semibold text-sm">{inst.symbol}</span>
                </div>
                <span className={`text-xs font-medium ${positive ? 'text-green-400' : 'text-red-400'}`}>
                  {positive ? '+' : ''}{inst.change_pct?.toFixed(2)}%
                </span>
              </div>
              <div className="text-xl font-bold font-mono">
                {inst.current_price?.toFixed(2) || '-'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {inst.trend} | {inst.sentiment}
              </div>
            </button>
          )
        })}
      </div>

      {/* Detail Panel */}
      {selected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 flex-wrap">
              {kindIcons[selected.kind] || <Activity className="w-5 h-5" />}
              {selected.symbol} — {selected.label}
              <DataQualityBadge a={selected} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selected.data_quality === 'synthetic' && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>The market feed is unavailable — the levels below would be <strong>simulated, not real</strong>. Don't trade on them; retry when the feed is live.</span>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Current Price</div>
                <div className="text-xl font-bold font-mono">{selected.current_price?.toFixed(selected.symbol === 'BTCUSD' ? 0 : 2)}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Change</div>
                <div className={`text-lg font-bold ${isPositive(selected.change_pct) ? 'text-green-400' : 'text-red-400'}`}>
                  {isPositive(selected.change_pct) ? '+' : ''}{selected.change_pct?.toFixed(2)}%
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Trend</div>
                <div className={`text-lg font-bold ${selected.trend === 'BULLISH' ? 'text-green-400' : selected.trend === 'BEARISH' ? 'text-red-400' : 'text-muted-foreground'}`}>
                  {selected.trend}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Sentiment</div>
                <div className="text-lg font-bold">{selected.sentiment}</div>
              </div>
            </div>

            {selected.reasoning && (
              <div className="mb-6 p-4 rounded-lg border border-primary/20 bg-primary/5">
                <div className="text-xs font-semibold text-primary uppercase tracking-wide mb-1">Reasoning</div>
                <p className="text-sm leading-relaxed">{selected.reasoning}</p>
              </div>
            )}

            {selected.news && selected.news.length > 0 && (
              <div className="mb-6">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">News that can move {selected.symbol}</div>
                <div className="space-y-1.5">
                  {selected.news.map((n, i) => (
                    <a key={i} href={n.link || '#'} target={n.link ? '_blank' : undefined} rel="noreferrer"
                       className="flex items-start gap-2 text-sm hover:text-primary">
                      <span className={`shrink-0 mt-0.5 text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        n.impact === 'high' ? 'bg-red-500/15 text-red-400' : n.impact === 'medium' ? 'bg-amber-500/15 text-amber-400' : 'bg-muted text-muted-foreground'
                      }`}>{n.impact}</span>
                      <span className="leading-tight">{n.title} <span className="text-muted-foreground">· {n.source}</span></span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">SMA 20</div>
                <div className="text-sm font-mono font-semibold">{selected.sma20?.toFixed(2) || '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">SMA 50</div>
                <div className="text-sm font-mono font-semibold">{selected.sma50?.toFixed(2) || '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Support</div>
                <div className="text-sm font-mono font-semibold text-green-400">{selected.support?.toFixed(2) || '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Resistance</div>
                <div className="text-sm font-mono font-semibold text-red-400">{selected.resistance?.toFixed(2) || '-'}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Volatility</div>
                <div className="text-sm font-semibold">{selected.volatility?.volatility_pct?.toFixed(2) || '-'}%</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Daily Range</div>
                <div className="text-sm font-semibold">{selected.volatility?.daily_range?.toFixed(2) || '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">ATR</div>
                <div className="text-sm font-semibold">{selected.volatility?.atr?.toFixed(2) || '-'}</div>
              </div>
            </div>

            {selected.key_levels && selected.key_levels.length > 0 && (
              <div>
                <div className="text-sm font-medium mb-2">Key Levels</div>
                <div className="flex gap-2 flex-wrap">
                  {selected.key_levels.map((level, i) => (
                    <span
                      key={i}
                      className={`text-xs px-2 py-1 rounded ${
                        level.type === 'support' ? 'bg-green-100 text-green-800' :
                        level.type === 'resistance' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {level.type}: {level.level.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Backtest + Monte Carlo — always visible; follows the selected instrument
          but has its own symbol picker so it works without selecting one. */}
      <BacktestPanel symbol={selected?.symbol} />

      {/* Correlation Matrix */}
      {correlation?.matrix && Object.keys(correlation.matrix).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Correlation Matrix</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="p-2 text-left">Symbol</th>
                    {correlation.symbols?.map((s: string) => (
                      <th key={s} className="p-2 text-center">{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {correlation.symbols?.map((sym1: string) => (
                    <tr key={sym1}>
                      <td className="p-2 font-semibold">{sym1}</td>
                      {correlation.symbols?.map((sym2: string) => {
                        const val = correlation.matrix?.[sym1]?.[sym2] ?? 0
                        const intensity = Math.abs(val)
                        const color = val > 0 ? `rgba(34, 197, 94, ${intensity * 0.3})` : `rgba(239, 68, 68, ${intensity * 0.3})`
                        return (
                          <td
                            key={sym2}
                            className="p-2 text-center font-mono"
                            style={{ backgroundColor: color }}
                          >
                            {val.toFixed(2)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
