import { useState, useEffect, useCallback } from 'react'
import { SUPPORTED_SYMBOLS } from '@/lib/instruments'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { researchApi, quantApi } from '@/api/client'
import BacktestPanel from '@/components/BacktestPanel'
import ForwardTests from '@/components/ForwardTests'
import StrategyLab from '@/components/StrategyLab'
import TradingPlan from '@/components/TradingPlan'
import {
  Activity, DollarSign, AlertTriangle, Shield, Globe, BarChart3, Layers,
  TrendingUp, TrendingDown, Zap, Clock, Target, HelpCircle,
  Loader2, FlaskConical, CheckCircle, XCircle, AlertCircle, ArrowRight, RefreshCw
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
  timestamp: string
}

interface AgentResult {
  agent: string
  symbol: string
  loading: boolean
  data: any
  error?: string
}

interface DecisionResult {
  symbol: string
  direction: string
  recommendation: string
  score: number
  max_score: number
  trend_alignment: string
  trend: string
  sr_proximity_pct: number
  sr_assessment: string
  volatility_regime: string
  volatility_assessment: string
  session: string
  session_optimal: boolean
  timestamp: string
}

const AGENTS = [
  { key: 'trend', label: 'Trend Analyzer', icon: TrendingUp, desc: 'SMA crossover, trend detection, momentum' },
  { key: 'volatility', label: 'Volatility Analyzer', icon: Activity, desc: 'ATR, Bollinger Bands, volatility regime' },
  { key: 'levels', label: 'S/R Detector', icon: Target, desc: 'Swing high/low analysis, key levels' },
  { key: 'correlation', label: 'Correlation Analyzer', icon: BarChart3, desc: 'Inter-market correlation matrix' },
  { key: 'session', label: 'Session Analyzer', icon: Clock, desc: 'Best trading hours per instrument' },
]

const SYMBOLS = SUPPORTED_SYMBOLS

export default function QuantLab() {
  const [instruments, setInstruments] = useState<InstrumentAnalysis[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [correlation, setCorrelation] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [demoMode, setDemoMode] = useState(false)

  const [agentResults, setAgentResults] = useState<AgentResult[]>([])
  const [decisionSymbol, setDecisionSymbol] = useState('EURUSD')
  const [decisionDirection, setDecisionDirection] = useState('long')
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null)
  const [decisionLoading, setDecisionLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [allRes, corrRes] = await Promise.all([
        researchApi.all(),
        researchApi.correlation(),
      ])
      const insts = allRes.data?.instruments || []
      if (!insts.length) {
        throw new Error('No instrument data returned from API. Yahoo Finance may be unreachable.')
      }
      setInstruments(insts)
      setCorrelation(corrRes.data)
      setDemoMode(false)
    } catch (err: any) {
      setError(err.message || 'Failed to load research data')
      setInstruments([])
      // Offer demo mode if API fails
      if (retryCount >= 1) {
        setDemoMode(true)
      }
    } finally {
      setLoading(false)
    }
  }, [retryCount])

  useEffect(() => {
    load()
  }, [load])

  const handleRetry = () => {
    setRetryCount(c => c + 1)
    load()
  }

  const enableDemo = () => {
    setDemoMode(true)
    setError(null)
    const mockInstruments: InstrumentAnalysis[] = SYMBOLS.map((sym, i) => ({
      symbol: sym,
      label: sym,
      kind: ['fx', 'index', 'metal', 'crypto', 'commodity'][i % 5],
      current_price: 100 + i * 10 + Math.random() * 5,
      change: (Math.random() - 0.5) * 2,
      change_pct: (Math.random() - 0.5) * 2,
      trend: ['BULLISH', 'BEARISH', 'NEUTRAL'][i % 3],
      sentiment: ['BULLISH', 'BEARISH', 'NEUTRAL'][i % 3],
      volatility: { atr: 0.5 + Math.random(), daily_range: 2 + Math.random() * 3, volatility_pct: 0.5 + Math.random() },
      support: 90 + i * 10,
      resistance: 110 + i * 10,
      dist_to_support: 2 + Math.random() * 3,
      dist_to_resistance: 2 + Math.random() * 3,
      key_levels: [{ level: 100 + i * 10, type: 'support' }, { level: 105 + i * 10, type: 'resistance' }],
      sma20: 100 + i * 10 - 1,
      sma50: 100 + i * 10 - 2,
      timestamp: new Date().toISOString(),
    }))
    setInstruments(mockInstruments)
  }

  const runAgent = useCallback(async (agentKey: string, symbol: string) => {
    if (!symbol) return
    setAgentResults((prev) => [
      ...prev.filter((r) => !(r.agent === agentKey && r.symbol === symbol)),
      { agent: agentKey, symbol, loading: true, data: null },
    ])
    try {
      let data: any = null
      if (agentKey === 'trend') {
        const res = await quantApi.trend(symbol)
        data = res.data
      } else if (agentKey === 'volatility') {
        const res = await quantApi.volatility(symbol)
        data = res.data
      } else if (agentKey === 'levels') {
        const res = await quantApi.levels(symbol)
        data = res.data
      } else if (agentKey === 'session') {
        const res = await quantApi.session(symbol)
        data = res.data
      } else if (agentKey === 'correlation') {
        const res = await researchApi.correlation()
        data = res.data
      }
      setAgentResults((prev) => [
        ...prev.filter((r) => !(r.agent === agentKey && r.symbol === symbol)),
        { agent: agentKey, symbol, loading: false, data },
      ])
    } catch (e: any) {
      setAgentResults((prev) => [
        ...prev.filter((r) => !(r.agent === agentKey && r.symbol === symbol)),
        { agent: agentKey, symbol, loading: false, data: null, error: e?.message || 'Failed' },
      ])
    }
  }, [])

  const runDecision = useCallback(async () => {
    if (!decisionSymbol) return
    setDecisionLoading(true)
    try {
      const res = await quantApi.decision(decisionSymbol, decisionDirection)
      setDecisionResult(res.data)
    } catch (e: any) {
      alert(e?.message || 'Decision analysis failed')
    } finally {
      setDecisionLoading(false)
    }
  }, [decisionSymbol, decisionDirection])

  // Default decision symbol to first instrument once loaded
  useEffect(() => {
    if (instruments.length > 0 && decisionSymbol === 'EURUSD') {
      setDecisionSymbol(instruments[0].symbol)
    }
  }, [instruments, decisionSymbol])

  const selected = instruments.find((i) => i.symbol === selectedSymbol)
  const isPositive = (val: number) => val >= 0

  // Default to first instrument once loaded
  useEffect(() => {
    if (instruments.length > 0 && !selectedSymbol) {
      setSelectedSymbol(instruments[0].symbol)
    }
  }, [instruments, selectedSymbol])

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

  const recommendationBadge = (rec: string) => {
    switch (rec) {
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

  const renderAgentResult = (result: AgentResult) => {
    if (result.loading) {
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          Running {AGENTS.find((a) => a.key === result.agent)?.label}...
        </div>
      )
    }
    if (result.error) {
      return (
        <div className="text-sm text-red-400 flex items-center gap-2 py-2">
          <XCircle className="w-4 h-4" />
          {result.error}
        </div>
      )
    }
    const d = result.data
    if (!d) return null

    if (result.agent === 'trend') {
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            {d.trend === 'BULLISH' ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : d.trend === 'BEARISH' ? <TrendingDown className="w-4 h-4 text-red-400" /> : <Activity className="w-4 h-4 text-muted-foreground" />}
            <span className="font-semibold">{d.trend}</span>
            <span className="text-xs text-muted-foreground">SMA20 {d.sma20} | SMA50 {d.sma50}</span>
          </div>
          <div className="text-xs text-muted-foreground">10h momentum: {d.momentum_10h}%</div>
        </div>
      )
    }

    if (result.agent === 'volatility') {
      const regimeColor = d.regime === 'EXTREME' ? 'text-red-400' : d.regime === 'HIGH' ? 'text-amber-400' : 'text-emerald-400'
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${regimeColor}`} />
            <span className={`font-semibold ${regimeColor}`}>{d.regime}</span>
            <span className="text-xs text-muted-foreground">ATR {d.atr}</span>
          </div>
          <div className="text-xs text-muted-foreground">Upper: {d.upper_band} | Lower: {d.lower_band}</div>
          <div className="text-xs text-muted-foreground">Dist to upper: {d.dist_to_upper_pct}% | lower: {d.dist_to_lower_pct}%</div>
        </div>
      )
    }

    if (result.agent === 'levels') {
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-3">
            <div className="text-emerald-400 font-semibold text-xs">S: {d.support}</div>
            <div className="text-red-400 font-semibold text-xs">R: {d.resistance}</div>
          </div>
          <div className="text-xs text-muted-foreground">Dist to S: {d.dist_to_support_pct}% | R: {d.dist_to_resistance_pct}%</div>
          {d.swing_highs?.length > 0 && (
            <div className="text-xs text-muted-foreground">Swing highs: {d.swing_highs.slice(0, 3).join(', ')}</div>
          )}
          {d.swing_lows?.length > 0 && (
            <div className="text-xs text-muted-foreground">Swing lows: {d.swing_lows.slice(0, 3).join(', ')}</div>
          )}
        </div>
      )
    }

    if (result.agent === 'session') {
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            {d.in_killzone ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <AlertCircle className="w-4 h-4 text-amber-400" />}
            <span className="font-semibold">{d.recommendation}</span>
          </div>
          <div className="text-xs text-muted-foreground">Best sessions: {d.best_sessions?.join(', ') || 'N/A'}</div>
          <div className="text-xs text-muted-foreground">UTC hour: {d.utc_hour}</div>
        </div>
      )
    }

    if (result.agent === 'correlation') {
      return (
        <div className="text-sm text-muted-foreground">
          Correlation matrix updated for {d.symbols?.length || 0} instruments.
        </div>
      )
    }

    return null
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <FlaskConical className="w-6 h-6 text-primary" />
          QuantLab
        </h1>
        <p className="text-muted-foreground">Loading instrument analysis...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-primary" />
            QuantLab
          </h1>
          <p className="text-muted-foreground">Quantitative research, agent analysis & trade decision support</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRetry}>
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh Data
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {demoMode && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Demo mode active — showing synthetic data. API data unavailable.</span>
          <Button variant="ghost" size="sm" className="h-6 text-xs ml-auto" onClick={handleRetry}>
            Try Real Data
          </Button>
        </div>
      )}

      {error && instruments.length === 0 && !demoMode && (
        <div className="p-6 rounded-lg border border-border bg-card text-center">
          <p className="text-muted-foreground mb-4">Unable to load instrument data from the API.</p>
          <div className="flex justify-center gap-3">
            <Button onClick={handleRetry}>
              <RefreshCw className="w-4 h-4 mr-2" /> Retry
            </Button>
            <Button variant="outline" onClick={enableDemo}>
              Use Demo Data
            </Button>
          </div>
        </div>
      )}

      {/* Backtest + Monte Carlo — measure the signal's real edge */}
      <BacktestPanel symbol={selected?.symbol} />

      {/* The app plans the trade: regime -> evidence-gated strategy -> setup */}
      <TradingPlan defaultSymbol={selected?.symbol} />

      {/* Classic quant strategies + ML baseline on the same honest harness */}
      <StrategyLab defaultSymbol={selected?.symbol} />

      {/* Live paper-forward test — validate a config on future candles */}
      <ForwardTests defaultSymbol={selected?.symbol} />

      {/* Quant Agents Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="w-5 h-5 text-amber-400" />
            Quant Agents
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 mb-3">
            <select
              className="px-2 py-1 border rounded-md bg-background text-sm"
              value={selectedSymbol || ''}
              onChange={(e) => setSelectedSymbol(e.target.value)}
            >
              {instruments.map((inst) => (
                <option key={inst.symbol} value={inst.symbol}>{inst.symbol} — {inst.label}</option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">
              {selected ? `${selected.trend} | ${selected.sentiment}` : 'Select instrument'}
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {AGENTS.map((agent) => {
              const Icon = agent.icon
              const result = agentResults.find((r) => r.agent === agent.key && r.symbol === selectedSymbol)
              return (
                <div key={agent.key} className="border rounded-lg p-3 bg-card hover:border-primary/30 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-md bg-primary/10">
                        <Icon className="w-4 h-4 text-primary" />
                      </div>
                      <div className="text-sm font-semibold">{agent.label}</div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs"
                      onClick={() => runAgent(agent.key, selectedSymbol || '')}
                      disabled={result?.loading || !selectedSymbol}
                    >
                      {result?.loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Run'}
                    </Button>
                  </div>
                  <div className="text-xs text-muted-foreground mb-2">{agent.desc}</div>
                  {result && (
                    <div className="border-t border-border/50 pt-2">
                      {renderAgentResult(result)}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Decision Helper */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <HelpCircle className="w-5 h-5 text-primary" />
            Should I Trade?
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-3 mb-4">
            <select
              className="px-3 py-2 border rounded-md bg-background text-sm"
              value={decisionSymbol}
              onChange={(e) => setDecisionSymbol(e.target.value)}
            >
              {instruments.map((inst) => (
                <option key={inst.symbol} value={inst.symbol}>{inst.symbol} — {inst.label}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                onClick={() => setDecisionDirection('long')}
                className={`px-3 py-2 rounded-md text-sm font-medium border transition-colors ${
                  decisionDirection === 'long'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <TrendingUp className="w-4 h-4 inline mr-1" /> Long
              </button>
              <button
                onClick={() => setDecisionDirection('short')}
                className={`px-3 py-2 rounded-md text-sm font-medium border transition-colors ${
                  decisionDirection === 'short'
                    ? 'bg-red-500/10 border-red-500/30 text-red-400'
                    : 'border-border bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <TrendingDown className="w-4 h-4 inline mr-1" /> Short
              </button>
            </div>
            <Button onClick={runDecision} disabled={decisionLoading} className="md:ml-auto">
              {decisionLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ArrowRight className="w-4 h-4 mr-2" />}
              Analyze
            </Button>
          </div>

          {decisionResult && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className={`px-3 py-1.5 rounded-full text-sm font-bold border ${recommendationBadge(decisionResult.recommendation)}`}>
                  {decisionResult.recommendation}
                </div>
                <div className="text-sm text-muted-foreground">
                  Score: {decisionResult.score} / {decisionResult.max_score}
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Trend Alignment</div>
                  <div className={`text-sm font-semibold ${decisionResult.trend_alignment === 'ALIGNED' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {decisionResult.trend_alignment}
                  </div>
                  <div className="text-xs text-muted-foreground">{decisionResult.trend}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <div className="text-xs text-muted-foreground mb-1">S/R Proximity</div>
                  <div className={`text-sm font-semibold ${decisionResult.sr_assessment === 'CLOSE' ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {decisionResult.sr_assessment}
                  </div>
                  <div className="text-xs text-muted-foreground">{decisionResult.sr_proximity_pct?.toFixed(2)}%</div>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Volatility</div>
                  <div className={`text-sm font-semibold ${decisionResult.volatility_assessment === 'SAFE' ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {decisionResult.volatility_assessment}
                  </div>
                  <div className="text-xs text-muted-foreground">{decisionResult.volatility_regime}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Session</div>
                  <div className={`text-sm font-semibold ${decisionResult.session_optimal ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {decisionResult.session_optimal ? 'OPTIMAL' : 'CAUTION'}
                  </div>
                  <div className="text-xs text-muted-foreground">{decisionResult.session}</div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
                  {positive ? '+' : ''}{(inst.change_pct ?? 0).toFixed(2)}%
                </span>
              </div>
              <div className="text-xl font-bold font-mono">
                {inst.current_price != null ? inst.current_price.toFixed(2) : '-'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {inst.trend || 'NEUTRAL'} | {inst.sentiment || 'NEUTRAL'}
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
              {selected.data_quality === 'synthetic' ? (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">⚠ simulated — not tradeable</span>
              ) : selected.data_quality === 'stale' ? (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">stale feed</span>
              ) : selected.data_quality === 'live' ? (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300/90 border border-emerald-500/20">live · {selected.data_source || 'source'}</span>
              ) : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Current Price</div>
                <div className="text-xl font-bold font-mono">
                  {selected.current_price != null ? selected.current_price.toFixed(selected.symbol === 'BTCUSD' ? 0 : 2) : '-'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Change</div>
                <div className={`text-lg font-bold ${isPositive(selected.change_pct ?? 0) ? 'text-green-400' : 'text-red-400'}`}>
                  {isPositive(selected.change_pct ?? 0) ? '+' : ''}{(selected.change_pct ?? 0).toFixed(2)}%
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Trend</div>
                <div className={`text-lg font-bold ${selected.trend === 'BULLISH' ? 'text-green-400' : selected.trend === 'BEARISH' ? 'text-red-400' : 'text-muted-foreground'}`}>
                  {selected.trend || 'NEUTRAL'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Sentiment</div>
                <div className="text-lg font-bold">{selected.sentiment || 'NEUTRAL'}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">SMA 20</div>
                <div className="text-sm font-mono font-semibold">{selected.sma20 != null ? selected.sma20.toFixed(2) : '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">SMA 50</div>
                <div className="text-sm font-mono font-semibold">{selected.sma50 != null ? selected.sma50.toFixed(2) : '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Support</div>
                <div className="text-sm font-mono font-semibold text-green-400">{selected.support != null ? selected.support.toFixed(2) : '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Resistance</div>
                <div className="text-sm font-mono font-semibold text-red-400">{selected.resistance != null ? selected.resistance.toFixed(2) : '-'}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Volatility</div>
                <div className="text-sm font-semibold">{(selected.volatility?.volatility_pct ?? 0).toFixed(2)}%</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">Daily Range</div>
                <div className="text-sm font-semibold">{selected.volatility?.daily_range != null ? selected.volatility.daily_range.toFixed(2) : '-'}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted">
                <div className="text-xs text-muted-foreground">ATR</div>
                <div className="text-sm font-semibold">{selected.volatility?.atr != null ? selected.volatility.atr.toFixed(2) : '-'}</div>
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
                        level.type === 'support' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
                        level.type === 'resistance' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300' :
                        'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
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
