import { useState, useEffect, useCallback } from 'react'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import SignalIntelligence from '@/components/SignalIntelligence'
import StrengthCalibration from '@/components/StrengthCalibration'
import Mt5ChartLevels from '@/components/Mt5ChartLevels'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { signalsApi } from '@/api/client'
import {
  Activity, TrendingUp, TrendingDown, Zap, RefreshCw, Loader2,
  AlertTriangle, Target, Shield, Eye, CheckCircle, XCircle,
  ArrowRight, Signal, Clock, Layers, BarChart3, Info
} from 'lucide-react'

interface ChecklistItem {
  key: string
  label: string
  passed: boolean
  description: string
  value?: string
}

interface SignalData {
  id?: string
  symbol: string
  sentiment: string
  score: number
  max_score: number
  quality: string
  bias_source?: string
  target_r?: number
  confluences: string[]
  checklist?: ChecklistItem[]
  entry_zone?: number
  stop_loss?: number
  targets?: (number | null)[]
  confidence: number
  session: string
  executed: boolean
  created_at: string
  expires_at: string
  htf_bias: string
  message?: string
}

interface SignalResponse {
  signal?: SignalData | null
  symbol?: string
  message?: string
  checklist?: ChecklistItem[]
  score?: number
  max_score?: number
  quality?: string
  confluences?: string[]
  sentiment?: string
  session?: string
  htf_bias?: string
}

const SYMBOLS = SUPPORTED_SYMBOLS

const qualityBadge = (quality: string) => {
  switch (quality) {
    case 'STRONG':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    case 'MODERATE':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    case 'WEAK':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    default:
      return 'bg-red-500/10 text-red-400 border-red-500/20'
  }
}

const confluenceIcon = (name: string) => {
  if (name.includes('Bias')) return <TrendingUp className="w-3 h-3" />
  if (name.includes('MSS')) return <Zap className="w-3 h-3" />
  if (name.includes('FVG') || name.includes('OB')) return <Target className="w-3 h-3" />
  if (name.includes('Liquidity')) return <Shield className="w-3 h-3" />
  if (name.includes('Premium')) return <Eye className="w-3 h-3" />
  if (name.includes('R_Target')) return <CheckCircle className="w-3 h-3" />
  return <Activity className="w-3 h-3" />
}

const checklistIcon = (key: string) => {
  if (key === 'htf_bias') return <TrendingUp className="w-3.5 h-3.5" />
  if (key === 'mss') return <Zap className="w-3.5 h-3.5" />
  if (key === 'fvg') return <Layers className="w-3.5 h-3.5" />
  if (key === 'ob') return <Target className="w-3.5 h-3.5" />
  if (key === 'liquidity') return <Shield className="w-3.5 h-3.5" />
  if (key === 'premium_discount') return <Eye className="w-3.5 h-3.5" />
  if (key === 'killzone') return <Clock className="w-3.5 h-3.5" />
  if (key === 'rr_viable') return <BarChart3 className="w-3.5 h-3.5" />
  if (key === 'mtf_alignment') return <Activity className="w-3.5 h-3.5" />
  return <Info className="w-3.5 h-3.5" />
}

const ICTCriteriaChecklist = ({ checklist, compact = false }: { checklist?: ChecklistItem[], compact?: boolean }) => {
  if (!checklist || checklist.length === 0) return null
  const passed = checklist.filter(c => c.passed)
  const failed = checklist.filter(c => !c.passed)

  return (
    <div className={`${compact ? 'space-y-1' : 'space-y-1.5'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold text-muted-foreground">ICT Criteria</span>
        <span className="text-xs text-emerald-400">{passed.length}</span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="text-xs text-red-400">{failed.length}</span>
        <span className="text-xs text-muted-foreground">of {checklist.length}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
        {checklist.map((item) => (
          <div
            key={item.key}
            className={`flex items-center gap-2 px-2 py-1 rounded-md text-xs border ${
              item.passed
                ? 'bg-emerald-500/5 border-emerald-500/10 text-emerald-400'
                : 'bg-red-500/5 border-red-500/10 text-red-400/70'
            }`}
            title={item.description}
          >
            {item.passed ? (
              <CheckCircle className="w-3 h-3 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="w-3 h-3 text-red-400/70 shrink-0" />
            )}
            {checklistIcon(item.key)}
            <span className={`truncate ${item.passed ? 'font-medium' : 'line-through opacity-60'}`}>
              {item.label}
            </span>
            {item.value && (
              <span className={`ml-auto text-[10px] px-1 py-0.5 rounded ${
                item.passed ? 'bg-emerald-500/10' : 'bg-red-500/10'
              }`}>
                {item.value}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Signals() {
  const [activeSignals, setActiveSignals] = useState<SignalData[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD')
  const [targetR, setTargetR] = useState(2)
  const [symbolSignal, setSymbolSignal] = useState<SignalResponse | null>(null)
  const [scanResults, setScanResults] = useState<SignalData[]>([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadActive = useCallback(async () => {
    try {
      setError(null)
      const res = await signalsApi.active()
      const data = res.data?.signals || []
      setActiveSignals(data.filter((s: any) => s && s.id))
    } catch (e: any) {
      setError(e?.message || 'Failed to load active signals')
    }
  }, [])

  const analyzeSymbol = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await signalsApi.analyze(selectedSymbol, { target_r: targetR })
      setSymbolSignal(res.data || null)
    } catch (e: any) {
      setError(e?.message || `Failed to analyze ${selectedSymbol}`)
    } finally {
      setLoading(false)
    }
  }, [selectedSymbol, targetR])

  const scanAll = useCallback(async () => {
    setScanning(true)
    setError(null)
    try {
      const res = await signalsApi.scan()
      const signals = res.data?.signals || []
      setScanResults(signals.filter((s: any) => s && s.id))
      await loadActive()
    } catch (e: any) {
      setError(e?.message || 'Scan failed')
    } finally {
      setScanning(false)
    }
  }, [loadActive])

  useEffect(() => {
    loadActive()
    const interval = setInterval(loadActive, 30000)
    return () => clearInterval(interval)
  }, [loadActive])

  const isBullish = (sentiment: string) => sentiment?.toLowerCase() === 'bullish'

  const renderSignalCard = (sig: SignalData, title?: string) => (
    <Card key={sig.id || sig.symbol} className="border-border/60">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            {isBullish(sig.sentiment) ? (
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-400" />
            )}
            <span className="font-bold">{sig.symbol}</span>
            {title && <span className="text-muted-foreground text-xs">{title}</span>}
          </div>
          <div className={`px-2 py-0.5 rounded-full text-xs font-bold border ${qualityBadge(sig.quality)}`}>
            {sig.quality} ({sig.score}/{sig.max_score})
          </div>
        </CardTitle>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Direction:{' '}
          {sig.bias_source === 'signal_intelligence'
            ? 'Signal Intelligence (news+technical+momentum+ICT)'
            : 'ICT structure'}
          {sig.target_r ? ` · targets at ${sig.target_r}R` : ''}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* ICT Criteria Checklist */}
        <ICTCriteriaChecklist checklist={sig.checklist} />

        {/* Confluences */}
        <div className="flex flex-wrap gap-1.5">
          {sig.confluences?.map((c) => (
            <span key={c} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-muted border border-border">
              {confluenceIcon(c)}
              {c}
            </span>
          )) || (
            <span className="text-xs text-muted-foreground">No confluences detected</span>
          )}
        </div>

        {/* Entry Zone */}
        {sig.entry_zone && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="p-2 rounded bg-muted text-center">
              <div className="text-xs text-muted-foreground">Entry</div>
              <div className="text-sm font-bold font-mono">{sig.entry_zone.toFixed(5)}</div>
            </div>
            {sig.stop_loss && (
              <div className="p-2 rounded bg-muted text-center">
                <div className="text-xs text-muted-foreground">SL</div>
                <div className="text-sm font-bold font-mono text-red-400">{sig.stop_loss.toFixed(5)}</div>
              </div>
            )}
            {sig.targets?.map((tp, i) => tp && (
              <div key={i} className="p-2 rounded bg-muted text-center">
                <div className="text-xs text-muted-foreground">TP{i + 1}</div>
                <div className="text-sm font-bold font-mono text-emerald-400">{tp.toFixed(5)}</div>
              </div>
            ))}
          </div>
        )}

        {/* Metadata */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>Session: {sig.session}</span>
          <span>Confidence: {(sig.confidence * 100).toFixed(0)}%</span>
          <span>HTF: {sig.htf_bias}</span>
          {sig.executed && (
            <span className="flex items-center gap-1 text-emerald-400">
              <CheckCircle className="w-3 h-3" /> Executed
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )

  const renderPartial = (resp: SignalResponse) => {
    if (!resp) return null
    const sig = resp.signal
    if (!sig) {
      const checklist = resp.checklist
      const score = resp.score ?? 0
      const maxScore = resp.max_score ?? 9
      const quality = resp.quality ?? 'NONE'
      return (
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardContent className="py-4 space-y-3">
            <div className="flex items-center gap-2 text-amber-400 text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-semibold">No Signal — {resp.symbol}</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${qualityBadge(quality)}`}>
                {quality} ({score}/{maxScore})
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{resp.message}</p>
            {checklist && checklist.length > 0 && (
              <ICTCriteriaChecklist checklist={checklist} />
            )}
          </CardContent>
        </Card>
      )
    }
    return renderSignalCard(sig, 'Analyzed')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Signal className="w-6 h-6 text-primary" />
          Signals
        </h1>
        <p className="text-muted-foreground">ICT confluence-based signal detection across timeframes</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <XCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Toolbar: pick a symbol, analyze it, or scan all */}
      <Card>
        <CardContent className="p-3">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Symbol</span>
              <select
                className="px-3 py-2 border rounded-md bg-background text-sm font-semibold"
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Target R</span>
              <select
                className="px-2 py-2 border rounded-md bg-background text-sm"
                value={targetR}
                onChange={(e) => setTargetR(Number(e.target.value))}
                title="Reward:risk of the proposed targets"
              >
                {[1.5, 2, 3].map((r) => <option key={r} value={r}>{r}R</option>)}
              </select>
            </div>
            <Button onClick={analyzeSymbol} disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ArrowRight className="w-4 h-4 mr-2" />}
              Analyze
            </Button>
            <Button variant="outline" onClick={scanAll} disabled={scanning} className="sm:ml-auto">
              {scanning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
              Scan All Symbols
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Selected symbol — the two engines side by side: ICT confluence
          checklist (structure) + news-driven intelligence (context). */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          {selectedSymbol} — analysis
        </h2>
        <div className="grid gap-4 xl:grid-cols-2 items-start">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" /> ICT Confluence
              </CardTitle>
            </CardHeader>
            <CardContent>
              {symbolSignal ? renderPartial(symbolSignal)
                : <p className="text-sm text-muted-foreground py-3 text-center">Click <strong>Analyze</strong> to run the ICT checklist.</p>}
            </CardContent>
          </Card>
          <SignalIntelligence symbol={selectedSymbol} />
        </div>
        {/* Measured win rate / expectancy per signal-strength tier. */}
        <StrengthCalibration symbol={selectedSymbol} />
        {/* Push the ICT zones to the user's MetaTrader 5 chart. */}
        <Mt5ChartLevels symbol={selectedSymbol} />
      </section>

      {/* Scan Results */}
      {scanResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Last Scan Results ({scanResults.length})</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-2">
            {scanResults.map((s) => renderSignalCard(s))}
          </CardContent>
        </Card>
      )}

      {/* Active Signals */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            Active Signals ({activeSignals.length})
            <Button variant="ghost" size="sm" onClick={loadActive} className="h-6 px-2 text-xs">
              <RefreshCw className="w-3 h-3 mr-1" /> Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {activeSignals.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No active signals. Run a scan or analyze a symbol to generate signals.
            </div>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {activeSignals.map((s) => renderSignalCard(s))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
