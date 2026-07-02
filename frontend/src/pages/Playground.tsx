import { useState, useEffect, useCallback } from 'react'
import { playgroundApi } from '@/api/client'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Globe,
  DollarSign,
  Coins,
  Droplets,
} from 'lucide-react'

interface PriceData {
  symbol: string
  label: string
  price: number
  change: number
  change_percent: number
  high: number
  low: number
  open: number
  volume: number
  prev_close: number
  timestamp: number
  kind: string
  digits: number
}

const kindIcons: Record<string, React.ReactNode> = {
  index: <BarChart3 className="w-5 h-5" />,
  fx: <DollarSign className="w-5 h-5" />,
  metal: <Coins className="w-5 h-5" />,
  crypto: <Globe className="w-5 h-5" />,
  commodity: <Droplets className="w-5 h-5" />,
}

const kindColors: Record<string, string> = {
  index: 'text-blue-400',
  fx: 'text-emerald-400',
  metal: 'text-yellow-400',
  crypto: 'text-purple-400',
  commodity: 'text-orange-400',
}

const kindBg: Record<string, string> = {
  index: 'bg-blue-500/10 border-blue-500/20',
  fx: 'bg-emerald-500/10 border-emerald-500/20',
  metal: 'bg-yellow-500/10 border-yellow-500/20',
  crypto: 'bg-purple-500/10 border-purple-500/20',
  commodity: 'bg-orange-500/10 border-orange-500/20',
}

export default function Playground() {
  const [prices, setPrices] = useState<PriceData[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [error, setError] = useState<string | null>(null)

  const fetchPrices = useCallback(async () => {
    try {
      setError(null)
      const response = await playgroundApi.getPrices()
      setPrices(response.data.prices || [])
      setLastUpdate(new Date())
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to fetch prices')
      console.error('Price fetch failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPrices()
    const interval = setInterval(fetchPrices, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [fetchPrices])

  const selectedPrice = prices.find((p) => p.symbol === selectedSymbol)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Playground</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Live market data and instrument analysis
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            Updated: {lastUpdate.toLocaleTimeString()}
          </span>
          <button
            onClick={fetchPrices}
            disabled={loading}
            className="px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Activity className="w-4 h-4 inline mr-1" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Price Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {loading && prices.length === 0
          ? Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="p-5 rounded-xl border border-border bg-card animate-pulse"
              >
                <div className="h-4 w-24 bg-muted rounded mb-3" />
                <div className="h-8 w-32 bg-muted rounded mb-2" />
                <div className="h-3 w-20 bg-muted rounded" />
              </div>
            ))
          : prices.map((price) => {
              const isPositive = price.change >= 0
              const isSelected = selectedSymbol === price.symbol

              return (
                <button
                  key={price.symbol}
                  onClick={() => setSelectedSymbol(isSelected ? null : price.symbol)}
                  className={`p-5 rounded-xl border text-left transition-all hover:scale-[1.02] ${
                    isSelected
                      ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                      : 'border-border bg-card hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={kindColors[price.kind] || 'text-muted-foreground'}>
                        {kindIcons[price.kind] || <Activity className="w-5 h-5" />}
                      </span>
                      <span className="text-sm font-semibold">{price.symbol}</span>
                    </div>
                    <span
                      className={`flex items-center gap-1 text-xs font-medium ${
                        isPositive ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {isPositive ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {isPositive ? '+' : ''}
                      {price.change.toFixed(price.digits)} ({isPositive ? '+' : ''}
                      {price.change_percent.toFixed(2)}%)
                    </span>
                  </div>

                  <div className="text-2xl font-bold tracking-tight">
                    {price.price.toFixed(price.digits)}
                  </div>

                  <div className="text-xs text-muted-foreground mt-2">
                    {price.label}
                  </div>
                </button>
              )
            })}
      </div>

      {/* Detail Panel */}
      {selectedPrice && (
        <div className={`p-6 rounded-xl border ${kindBg[selectedPrice.kind] || 'bg-card border-border'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className={kindColors[selectedPrice.kind] || 'text-muted-foreground'}>
                {kindIcons[selectedPrice.kind] || <Activity className="w-6 h-6" />}
              </span>
              <div>
                <h2 className="text-lg font-bold">{selectedPrice.symbol}</h2>
                <p className="text-sm text-muted-foreground">{selectedPrice.label}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold">{selectedPrice.price.toFixed(selectedPrice.digits)}</div>
              <div
                className={`text-sm font-medium ${
                  selectedPrice.change >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {selectedPrice.change >= 0 ? '+' : ''}
                {selectedPrice.change.toFixed(selectedPrice.digits)} ({selectedPrice.change >= 0 ? '+' : ''}
                {selectedPrice.change_percent.toFixed(2)}%)
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">Open</div>
              <div className="text-sm font-mono font-semibold">
                {selectedPrice.open.toFixed(selectedPrice.digits)}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">High</div>
              <div className="text-sm font-mono font-semibold text-green-400">
                {selectedPrice.high.toFixed(selectedPrice.digits)}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">Low</div>
              <div className="text-sm font-mono font-semibold text-red-400">
                {selectedPrice.low.toFixed(selectedPrice.digits)}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">Volume</div>
              <div className="text-sm font-mono font-semibold">
                {selectedPrice.volume.toLocaleString()}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">Previous Close</div>
              <div className="text-sm font-mono font-semibold">
                {selectedPrice.prev_close.toFixed(selectedPrice.digits)}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-background/50">
              <div className="text-xs text-muted-foreground mb-1">Kind</div>
              <div className="text-sm font-semibold capitalize">{selectedPrice.kind}</div>
            </div>
          </div>
        </div>
      )}

      {/* Info Card */}
      <div className="p-4 rounded-lg border border-border bg-card/50 text-sm text-muted-foreground">
        <p>
          <strong className="text-foreground">Data Source:</strong> Prices are fetched from Yahoo Finance
          via yfinance. Data is cached for 30 seconds to avoid rate limiting. Prices may be delayed.
        </p>
        <p className="mt-2">
          <strong className="text-foreground">Instruments:</strong> NQ1! (Nasdaq), ES1! (S&P 500), EUR/USD,
          GBP/USD, XAU/USD (Gold), USD/JPY, BTC/USD, CL1! (Crude Oil).
        </p>
      </div>
    </div>
  )
}
