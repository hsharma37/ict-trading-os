import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { ictApi } from '@/api/client'
import { Layers, RefreshCw, AlertTriangle } from 'lucide-react'

interface Zone {
  type: string; kind: string; direction: string; timeframe: string
  high: number; low: number; mid: number; confidence?: number
  position: 'above' | 'below' | 'inside'; distance_pips: number; distance_pct?: number
}
interface Levels {
  symbol: string; current_price: number | null; synthetic?: boolean
  dealing_range?: { high: number; low: number; equilibrium: number } | null
  premium_discount?: string; zones: Zone[]; count: number; total_detected?: number
}

const TYPE_LABEL: Record<string, string> = {
  OB: 'Order Block', FVG: 'Fair Value Gap', LIQUIDITY: 'Liquidity', MSS: 'Structure',
}
const dirCls = (d: string) => (d === 'bullish' ? 'text-emerald-400' : 'text-red-400')
const fmt = (n: number, sym: string) => n.toFixed(sym === 'BTCUSD' ? 1 : sym === 'USDJPY' ? 3 : sym === 'XAUUSD' ? 2 : 5)

/** Vertical price ladder: zones drawn as bands positioned by price, current
 *  price marker + equilibrium line. Gives an at-a-glance "where are the levels". */
function Ladder({ data }: { data: Levels }) {
  const price = data.current_price
  if (!price || !data.zones.length) return null
  const all = [price, ...data.zones.flatMap((z) => [z.high, z.low]),
    ...(data.dealing_range ? [data.dealing_range.high, data.dealing_range.low] : [])]
  const max = Math.max(...all), min = Math.min(...all)
  const span = max - min || 1
  const H = Math.max(220, Math.min(460, data.zones.length * 26))
  const W = 320
  const y = (p: number) => H - ((p - min) / span) * H
  const eq = data.dealing_range?.equilibrium

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 460 }}>
      {/* zones */}
      {data.zones.map((z, i) => {
        const yHi = y(z.high), yLo = y(z.low)
        const h = Math.max(2, yLo - yHi)
        const col = z.direction === 'bullish' ? '16,185,129' : '239,68,68'
        return (
          <g key={i}>
            <rect x={70} y={yHi} width={W - 80} height={h}
              fill={`rgba(${col},0.14)`} stroke={`rgba(${col},0.5)`} strokeWidth={z.kind === 'line' ? 0 : 0.5} />
            {z.kind === 'line' && <line x1={70} y1={y(z.mid)} x2={W - 10} y2={y(z.mid)} stroke={`rgba(${col},0.7)`} strokeDasharray="3" />}
            <text x={66} y={y(z.mid) + 3} textAnchor="end" fontSize="8" fill="currentColor" opacity="0.7">
              {z.type} {z.timeframe}
            </text>
          </g>
        )
      })}
      {/* equilibrium */}
      {eq != null && (
        <g>
          <line x1={70} y1={y(eq)} x2={W - 10} y2={y(eq)} stroke="currentColor" strokeOpacity="0.3" strokeDasharray="6" />
          <text x={W - 10} y={y(eq) - 2} textAnchor="end" fontSize="8" fill="currentColor" opacity="0.5">EQ {fmt(eq, data.symbol)}</text>
        </g>
      )}
      {/* current price */}
      <line x1={70} y1={y(price)} x2={W} y2={y(price)} stroke="#eab308" strokeWidth="1.5" />
      <text x={68} y={y(price) + 3} textAnchor="end" fontSize="9" fontWeight="bold" fill="#eab308">{fmt(price, data.symbol)}</text>
    </svg>
  )
}

export default function LiveIctLevels({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Levels | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await ictApi.levels(symbol)
      setData(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load levels')
    } finally { setLoading(false) }
  }, [symbol])

  useEffect(() => { load() }, [load])

  const above = (data?.zones || []).filter((z) => z.position === 'above')
  const inside = (data?.zones || []).filter((z) => z.position === 'inside')
  const below = (data?.zones || []).filter((z) => z.position === 'below')

  const row = (z: Zone) => (
    <div key={`${z.type}${z.timeframe}${z.mid}`} className="flex items-center justify-between gap-2 py-1 text-sm border-b border-border/40">
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${z.direction === 'bullish' ? 'bg-emerald-400' : 'bg-red-400'}`} />
        <span className={`font-medium ${dirCls(z.direction)}`}>{TYPE_LABEL[z.type] || z.type}</span>
        <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground">{z.timeframe}</span>
      </div>
      <div className="font-mono text-xs text-right">
        {z.kind === 'zone' ? `${fmt(z.low, data!.symbol)} – ${fmt(z.high, data!.symbol)}` : fmt(z.mid, data!.symbol)}
        <span className="text-muted-foreground ml-2">{z.distance_pips === 0 ? 'at price' : `${z.distance_pips}p`}</span>
      </div>
    </div>
  )

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Layers className="w-4 h-4 text-primary" /> Live ICT Levels — {symbol}
          {data?.premium_discount && data.premium_discount !== 'unknown' && (
            <span className={`text-[11px] px-2 py-0.5 rounded-full border ${data.premium_discount === 'premium' ? 'bg-red-500/10 text-red-300 border-red-500/30' : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'}`}>
              {data.premium_discount} (vs equilibrium)
            </span>
          )}
        </CardTitle>
        <button onClick={load} className="text-muted-foreground hover:text-foreground"><RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /></button>
      </CardHeader>
      <CardContent>
        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}
        {data?.synthetic && (
          <div className="mb-3 p-2 rounded bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Simulated data — these levels are not real.
          </div>
        )}
        {data && !data.synthetic && data.zones.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">No ICT zones detected near price right now.</p>
        )}
        {data && data.zones.length > 0 && (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="text-muted-foreground"><Ladder data={data} /></div>
            <div className="space-y-2 text-sm">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-red-300/80 mb-0.5">Resistance above ({above.length})</div>
                {above.length ? above.map(row) : <p className="text-xs text-muted-foreground">none nearby</p>}
              </div>
              {inside.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-yellow-300/80 mb-0.5">Price is inside ({inside.length})</div>
                  {inside.map(row)}
                </div>
              )}
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-300/80 mb-0.5">Support below ({below.length})</div>
                {below.length ? below.map(row) : <p className="text-xs text-muted-foreground">none nearby</p>}
              </div>
            </div>
          </div>
        )}
        {data?.total_detected != null && data.total_detected > data.count && (
          <p className="text-[11px] text-muted-foreground mt-2">Showing the {data.count} nearest of {data.total_detected} detected zones. Distances in pips from the current price. Zones = OB/FVG ranges; dashed lines = structure/liquidity levels.</p>
        )}
      </CardContent>
    </Card>
  )
}
