import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { signalsApi } from '@/api/client'
import {
  Zap, Activity, AlertTriangle, ArrowUpRight, ArrowDownRight, RefreshCw
} from 'lucide-react'

interface Signal {
  id: string
  symbol: string
  sentiment: string
  score: number
  max_score: number
  confluences: string[]
  entry_zone: number | null
  stop_loss: number | null
  targets: (number | null)[]
  confidence: number
  session: string
  executed: boolean
  created_at: string
  expires_at: string
}

const INSTRUMENTS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!']

export default function Suggestions() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [activeSignals, setActiveSignals] = useState<Signal[]>([])
  const [scanning, setScanning] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD')
  const [error, setError] = useState<string | null>(null)
  const [lastScan, setLastScan] = useState<Date | null>(null)

  const fetchSignals = useCallback(async () => {
    try {
      const res = await signalsApi.active()
      const active = res.data?.signals || []
      setActiveSignals(active.filter((s: any) => s))
    } catch (e) {
      console.error('Failed to fetch active signals', e)
    }
  }, [])

  const scan = async () => {
    setScanning(true)
    setError(null)
    try {
      const res = await signalsApi.scan()
      const found = res.data?.signals || []
      setSignals(prev => [...found, ...prev].slice(0, 50))
      setLastScan(new Date())
      fetchSignals()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const analyzeOne = async () => {
    setScanning(true)
    setError(null)
    try {
      const res = await signalsApi.analyze(selectedSymbol)
      const sig = res.data?.signal
      if (sig) {
        setSignals(prev => [sig, ...prev].slice(0, 50))
      } else {
        setError(`No valid signal for ${selectedSymbol}. Setup below confluence threshold.`)
      }
      fetchSignals()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Analysis failed')
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    fetchSignals()
  }, [fetchSignals])

  const renderSignal = (signal: Signal, isActive: boolean = false) => {
    const bullish = signal.sentiment === 'bullish'
    const scorePct = (signal.score / signal.max_score) * 100

    return (
      <div key={signal.id} className={`p-4 rounded-xl border ${isActive ? 'border-primary bg-primary/5' : 'border-border bg-card'}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-1 rounded font-bold ${
              bullish ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}>
              {bullish ? <ArrowUpRight className="w-3 h-3 inline mr-1" /> : <ArrowDownRight className="w-3 h-3 inline mr-1" />}
              {signal.sentiment.toUpperCase()}
            </span>
            <span className="font-bold text-lg">{signal.symbol}</span>
            <span className="text-xs text-muted-foreground">{signal.session}</span>
          </div>
          <div className="text-sm font-bold">
            Score: {signal.score}/{signal.max_score} ({scorePct.toFixed(0)}%)
          </div>
        </div>

        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-xs mb-3">
          <div className="p-2 rounded bg-muted">
            <div className="text-muted-foreground">Entry</div>
            <div className="font-mono font-semibold">{signal.entry_zone?.toFixed(5) || '-'}</div>
          </div>
          <div className="p-2 rounded bg-muted">
            <div className="text-muted-foreground">SL</div>
            <div className="font-mono font-semibold text-red-400">{signal.stop_loss?.toFixed(5) || '-'}</div>
          </div>
          {signal.targets?.filter(Boolean).map((t, i) => (
            <div key={i} className="p-2 rounded bg-muted">
              <div className="text-muted-foreground">TP{i + 1}</div>
              <div className="font-mono font-semibold text-green-400">{t?.toFixed(5) || '-'}</div>
            </div>
          ))}
        </div>

        <div className="flex gap-1 flex-wrap mb-2">
          {signal.confluences?.map((c, i) => (
            <span key={i} className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
              {c.replace(/_/g, ' ')}
            </span>
          ))}
        </div>

        <div className="text-xs text-muted-foreground">
          Confidence: {(signal.confidence * 100).toFixed(1)}% | Expires: {new Date(signal.expires_at).toLocaleTimeString()}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Signals</h1>
        <p className="text-muted-foreground">ICT-based pattern detection and trade suggestions</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-center">
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="px-3 py-2 border rounded-md bg-background text-sm"
            >
              {INSTRUMENTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <Button
              onClick={analyzeOne}
              disabled={scanning}
              variant="outline"
              className="text-sm"
            >
              <Activity className="w-4 h-4 mr-2" />
              {scanning ? 'Analyzing...' : `Analyze ${selectedSymbol}`}
            </Button>
            <Button
              onClick={scan}
              disabled={scanning}
              className="text-sm"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Scanning...' : 'Scan All'}
            </Button>
            {lastScan && (
              <span className="text-xs text-muted-foreground">
                Last scan: {lastScan.toLocaleTimeString()}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Active</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeSignals.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Bullish</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-400">
              {activeSignals.filter(s => s.sentiment === 'bullish').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Bearish</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-400">
              {activeSignals.filter(s => s.sentiment === 'bearish').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{signals.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Active Signals */}
      {activeSignals.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Active Signals</h2>
          {activeSignals.map(s => renderSignal(s, true))}
        </div>
      )}

      {/* Signal History */}
      {signals.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Recent Signals</h2>
          <div className="space-y-3">
            {signals.slice(0, 10).map(s => renderSignal(s))}
          </div>
        </div>
      )}

      {activeSignals.length === 0 && signals.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No signals detected yet. Click "Scan All" or "Analyze" to find ICT patterns.</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
