import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { telegramApi } from '@/api/client'
import {
  CheckCircle2, Bot, RefreshCw, ArrowUpRight, ArrowDownRight, AlertTriangle,
  TrendingUp, Hash, FileText, Zap, MessageSquare, Send
} from 'lucide-react'

interface TelegramSignal {
  id: string
  source_channel: string
  raw_text: string
  parsed: boolean
  symbol: string | null
  side: string | null
  entry_prices: number[]
  stop_loss: number | null
  take_profits: number[]
  strategy: string | null
  confidence: 'high' | 'medium' | 'low'
  acknowledged: boolean
  auto_traded: boolean
  trade_id: string | null
  created_at: string
  parsed_at: string | null
}

interface SignalStats {
  total: number
  parsed: number
  acknowledged: number
  auto_traded: number
  configured: boolean
  channel_id: string
  source_channel?: string
  source_poll_available?: boolean
  last_poll_time: string | null
}

export default function TelegramFeed() {
  const [signals, setSignals] = useState<TelegramSignal[]>([])
  const [stats, setStats] = useState<SignalStats | null>(null)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tokenInput, setTokenInput] = useState('')
  const [channelInput, setChannelInput] = useState('')
  const [configuring, setConfiguring] = useState(false)
  const [riskPct, setRiskPct] = useState(1.0)
  const [accountBalance, setAccountBalance] = useState(10000)

  const fetchSignals = useCallback(async () => {
    try {
      const res = await telegramApi.signals(50)
      const list = res.data?.signals || []
      setSignals(list.filter((s: any) => s))
    } catch (e: any) {
      console.error('Failed to fetch signals', e)
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await telegramApi.stats()
      setStats(res.data)
      // Source-channel polling (t.me/s/<channel>) needs no bot token, so only
      // warn when neither a bot nor a source channel is available.
      if (!res.data?.configured && !res.data?.source_poll_available) {
        setError('No Telegram source configured. Set a bot token/channel below, or configure TELEGRAM_SOURCE_CHANNEL.')
      } else {
        setError(null)
      }
    } catch (e: any) {
      console.error('Failed to fetch stats', e)
    }
  }, [])

  const poll = async () => {
    setPolling(true)
    setError(null)
    try {
      const res = await telegramApi.poll()
      if (res.data?.ok) {
        await fetchSignals()
        await fetchStats()
      } else {
        setError(res.data?.error || 'Poll failed')
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Poll failed')
    } finally {
      setPolling(false)
    }
  }

  const acknowledge = async (id: string) => {
    try {
      await telegramApi.acknowledge(id)
      setSignals(prev => prev.map(s => s.id === id ? { ...s, acknowledged: true } : s))
      await fetchStats()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Acknowledge failed')
    }
  }

  const autoTrade = async (id: string) => {
    try {
      await telegramApi.autoTrade(id, { account_balance: accountBalance, risk_pct: riskPct })
      setSignals(prev => prev.map(s => s.id === id ? { ...s, auto_traded: true } : s))
      await fetchStats()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Auto-trade failed')
    }
  }

  const configure = async () => {
    if (!tokenInput.trim() || !channelInput.trim()) return
    setConfiguring(true)
    try {
      await telegramApi.configure({ token: tokenInput.trim(), channel_id: channelInput.trim() })
      setTokenInput('')
      setChannelInput('')
      await fetchStats()
      await fetchSignals()
      setError(null)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Configuration failed')
    } finally {
      setConfiguring(false)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchSignals()
  }, [fetchStats, fetchSignals])

  useEffect(() => {
    const interval = setInterval(() => {
      fetchStats()
      fetchSignals()
    }, 10000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchSignals])

  const confidenceColor = (c: string) => {
    if (c === 'high') return 'border-green-500/50 bg-green-500/5'
    if (c === 'medium') return 'border-yellow-500/50 bg-yellow-500/5'
    return 'border-red-500/50 bg-red-500/5'
  }

  const confidenceBadge = (c: string) => {
    if (c === 'high') return 'bg-green-500/20 text-green-400'
    if (c === 'medium') return 'bg-yellow-500/20 text-yellow-400'
    return 'bg-red-500/20 text-red-400'
  }

  const sideIcon = (side: string | null) => {
    if (side === 'BUY') return <ArrowUpRight className="w-4 h-4 text-green-400" />
    if (side === 'SELL') return <ArrowDownRight className="w-4 h-4 text-red-400" />
    return <AlertTriangle className="w-4 h-4 text-muted-foreground" />
  }

  const sideBadge = (side: string | null) => {
    if (side === 'BUY') return 'bg-green-500/20 text-green-400'
    if (side === 'SELL') return 'bg-red-500/20 text-red-400'
    return 'bg-muted text-muted-foreground'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Telegram Signals</h1>
          <p className="text-muted-foreground">Live feed from your Telegram channel with auto-trade support</p>
        </div>
        {stats?.source_channel && (
          <a
            href={`https://t.me/s/${stats.source_channel}`}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/10 border border-sky-500/20 text-sky-400 hover:bg-sky-500/20"
            title="Polled automatically every hour"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
            @{stats.source_channel} · hourly
          </a>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Parsed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-400">{stats?.parsed ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Acknowledged</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-400">{stats?.acknowledged ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Auto-Traded</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-400">{stats?.auto_traded ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Configuration */}
      {(!stats?.configured) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="w-5 h-5 text-primary" />
              Configure Telegram Bot
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Bot Token</label>
                <input
                  type="password"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="123456789:ABC..."
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Channel / Chat ID</label>
                <input
                  type="text"
                  value={channelInput}
                  onChange={(e) => setChannelInput(e.target.value)}
                  placeholder="-1001234567890"
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                />
              </div>
            </div>
            <Button onClick={configure} disabled={configuring || !tokenInput || !channelInput}>
              <Send className="w-4 h-4 mr-2" />
              {configuring ? 'Saving...' : 'Save Configuration'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-center">
            <Button onClick={poll} disabled={polling || !stats?.configured}>
              <RefreshCw className={`w-4 h-4 mr-2 ${polling ? 'animate-spin' : ''}`} />
              {polling ? 'Polling...' : 'Manual Poll'}
            </Button>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Risk %:</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="5"
                value={riskPct}
                onChange={(e) => setRiskPct(parseFloat(e.target.value) || 1)}
                className="w-20 px-2 py-1 border rounded-md bg-background text-sm"
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Balance:</span>
              <input
                type="number"
                step="100"
                value={accountBalance}
                onChange={(e) => setAccountBalance(parseFloat(e.target.value) || 10000)}
                className="w-28 px-2 py-1 border rounded-md bg-background text-sm"
              />
            </div>
            {stats?.last_poll_time && (
              <span className="text-xs text-muted-foreground ml-auto">
                Last poll: {new Date(stats.last_poll_time).toLocaleTimeString()}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Signals */}
      <div className="space-y-3">
        {signals.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No Telegram signals yet. Click "Manual Poll" to fetch messages.</p>
            </CardContent>
          </Card>
        )}

        {signals.map((signal) => (
          <div
            key={signal.id}
            className={`rounded-xl border p-4 transition-colors ${confidenceColor(signal.confidence)}`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs px-2 py-1 rounded font-bold flex items-center gap-1 ${sideBadge(signal.side)}`}>
                  {sideIcon(signal.side)}
                  {signal.side ?? 'UNKNOWN'}
                </span>
                <span className="font-bold text-lg">{signal.symbol ?? '—'}</span>
                <span className="text-xs text-muted-foreground">#{signal.id}</span>
                <span className={`text-xs px-2 py-0.5 rounded font-semibold ${confidenceBadge(signal.confidence)}`}>
                  {signal.confidence.toUpperCase()} CONFIDENCE
                </span>
                {signal.acknowledged && (
                  <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    ACK
                  </span>
                )}
                {signal.auto_traded && (
                  <span className="text-xs px-2 py-0.5 rounded bg-green-500/20 text-green-400 flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" />
                    TRADED
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-xs mb-3">
              <div className="p-2 rounded bg-muted">
                <div className="text-muted-foreground">Entry</div>
                <div className="font-mono font-semibold">
                  {signal.entry_prices?.length > 0 ? signal.entry_prices.map(p => p.toFixed(5)).join(', ') : '-'}
                </div>
              </div>
              <div className="p-2 rounded bg-muted">
                <div className="text-muted-foreground">SL</div>
                <div className="font-mono font-semibold text-red-400">
                  {signal.stop_loss?.toFixed(5) ?? '-'}
                </div>
              </div>
              {signal.take_profits?.map((tp, i) => (
                <div key={i} className="p-2 rounded bg-muted">
                  <div className="text-muted-foreground">TP{i + 1}</div>
                  <div className="font-mono font-semibold text-green-400">{tp.toFixed(5)}</div>
                </div>
              ))}
            </div>

            <div className="flex gap-1 flex-wrap mb-2">
              {signal.strategy?.split(',').map((s, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                  {s.trim()}
                </span>
              ))}
            </div>

            <div className="p-2 rounded bg-muted/50 text-xs text-muted-foreground mb-3 line-clamp-3">
              {signal.raw_text}
            </div>

            <div className="flex gap-2 flex-wrap">
              {!signal.acknowledged && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => acknowledge(signal.id)}
                >
                  <CheckCircle2 className="w-4 h-4 mr-1" />
                  Acknowledge
                </Button>
              )}
              {!signal.auto_traded && signal.parsed && (
                <Button
                  size="sm"
                  onClick={() => autoTrade(signal.id)}
                  disabled={!signal.symbol || !signal.side}
                >
                  <Zap className="w-4 h-4 mr-1" />
                  Auto-Trade
                </Button>
              )}
              {signal.trade_id && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Hash className="w-3 h-3" />
                  Trade {signal.trade_id}
                </span>
              )}
              <span className="text-xs text-muted-foreground ml-auto flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {new Date(signal.created_at).toLocaleTimeString()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
