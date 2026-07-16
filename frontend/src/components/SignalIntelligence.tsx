import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { signalsApi } from '@/api/client'
import {
  Brain, TrendingUp, TrendingDown, Minus, Newspaper, Lightbulb, RefreshCw, AlertTriangle,
} from 'lucide-react'

interface Factor { name: string; direction: string; weight: number; detail: string }
interface NewsRef { title: string; impact: string; source: string; timestamp?: string; link?: string }
interface Intel {
  symbol: string
  signal: 'BUY' | 'SELL' | 'NEUTRAL'
  confidence: string
  confidence_score: number
  confidence_basis?: string
  data_quality?: 'live' | 'stale' | 'synthetic'
  data_source?: string
  unavailable?: boolean
  score: number
  news_sentiment: { score: number; label: string; items_scored: number; contributors: any[]; method?: string }
  technical: any
  ict: { rule: string; concepts: string[]; kb_source?: string }
  factors: Factor[]
  reasoning: string
  suggestions: string[]
  news: NewsRef[]
}

const dirColor = (d: string) =>
  d === 'BUY' || d === 'bullish' || d === 'long' ? 'text-emerald-400'
    : d === 'SELL' || d === 'bearish' || d === 'short' ? 'text-red-400'
      : 'text-muted-foreground'

const dirBg = (d: string) =>
  d === 'BUY' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    : d === 'SELL' ? 'bg-red-500/15 text-red-400 border-red-500/30'
      : 'bg-muted text-muted-foreground border-border'

export default function SignalIntelligence({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Intel | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await signalsApi.intelligence(symbol)
      setData(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to generate signal')
    } finally {
      setLoading(false)
    }
  }, [symbol])

  useEffect(() => { load() }, [load])

  const Arrow = data?.signal === 'BUY' ? TrendingUp : data?.signal === 'SELL' ? TrendingDown : Minus

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Brain className="w-4 h-4 text-primary" />
          Signal Intelligence — {symbol}
          <span className="text-xs font-normal text-muted-foreground">news sentiment + technicals + ICT</span>
        </CardTitle>
        <button onClick={load} className="text-muted-foreground hover:text-foreground" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}
        {!data && loading && <p className="text-sm text-muted-foreground">Analysing news + price + ICT…</p>}
        {data && data.data_quality === 'synthetic' && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            ⚠ Live market data is unavailable, so no reliable signal can be generated — technicals would be simulated. News sentiment below is still real.
          </div>
        )}
        {data && (
          <>
            {/* Verdict */}
            <div className="flex items-center gap-4 flex-wrap">
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border font-bold ${dirBg(data.signal)}`}>
                <Arrow className="w-5 h-5" /> {data.signal}
              </div>
              <div className="text-sm" title={data.confidence_basis || ''}>
                <span className="text-muted-foreground">Confidence </span>
                <span className="font-semibold capitalize">{data.confidence}</span>
                <span className="text-muted-foreground"> ({data.confidence_score}/100)</span>
                <span className="text-muted-foreground text-[10px] ml-1 align-top">ⓘ heuristic</span>
              </div>
              <div className="text-sm" title={data.news_sentiment.method ? 'Lexicon + negation over headline & summary — a rule-based heuristic, not a trained NLP model' : ''}>
                <span className="text-muted-foreground">News </span>
                <span className={`font-semibold ${dirColor(data.news_sentiment.label)}`}>
                  {data.news_sentiment.label} ({data.news_sentiment.score >= 0 ? '+' : ''}{data.news_sentiment.score})
                </span>
              </div>
              {data.data_quality && data.data_quality !== 'synthetic' && (
                <span className={`text-[11px] px-2 py-0.5 rounded-full border ${data.data_quality === 'stale' ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-emerald-500/10 text-emerald-300/90 border-emerald-500/20'}`}>
                  {data.data_quality === 'stale' ? 'stale feed' : `live · ${data.data_source || 'source'}`}
                </span>
              )}
            </div>

            {/* Reasoning */}
            <div className="p-3 rounded-lg border border-primary/20 bg-primary/5">
              <div className="text-xs font-semibold text-primary uppercase tracking-wide mb-1">Reasoning</div>
              <p className="text-sm leading-relaxed">{data.reasoning}</p>
            </div>

            {/* Factors */}
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Influencing factors</div>
              <div className="space-y-1.5">
                {data.factors.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <span className={`shrink-0 w-16 text-xs font-medium ${dirColor(f.direction)}`}>{f.direction}</span>
                    <span className="shrink-0 font-medium w-28">{f.name}</span>
                    <span className="text-muted-foreground flex-1">{f.detail}{f.weight ? ` (weight ${Math.round(f.weight * 100)}%)` : ''}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* ICT */}
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">ICT playbook</div>
              {data.ict.concepts?.length > 0 && (
                <div className="flex gap-1.5 flex-wrap mb-1.5">
                  {data.ict.concepts.map((c) => (
                    <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">{c}</span>
                  ))}
                </div>
              )}
              <p className="text-sm text-muted-foreground">{data.ict.rule}</p>
            </div>

            {/* Suggestions */}
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                <Lightbulb className="w-3.5 h-3.5" /> Suggestions
              </div>
              <ul className="space-y-1">
                {data.suggestions.map((s, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className="text-primary mt-0.5">›</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* News basis */}
            {data.news.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                  <Newspaper className="w-3.5 h-3.5" /> News the read is based on
                </div>
                <div className="space-y-1">
                  {data.news.map((n, i) => (
                    <a key={i} href={n.link || '#'} target={n.link ? '_blank' : undefined} rel="noreferrer"
                       className="flex items-start gap-2 text-xs hover:text-primary">
                      <span className={`shrink-0 mt-0.5 px-1.5 py-0.5 rounded font-bold uppercase text-[9px] ${
                        n.impact === 'high' ? 'bg-red-500/15 text-red-400' : 'bg-amber-500/15 text-amber-400'
                      }`}>{n.impact}</span>
                      <span className="leading-tight">{n.title} <span className="text-muted-foreground">· {n.source}</span></span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
