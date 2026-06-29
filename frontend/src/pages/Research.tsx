import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { apiClient } from '@/api/client'

export default function Research() {
  const [response, setResponse] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'backtest' | 'montecarlo' | 'backtrader'>('backtest')

  const runBacktest = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.post('/api/v1/research/backtest', {
        strategy: 'sma-crossover',
        symbol: 'EURUSD',
        timeframe: '1h',
        start: '2024-01-01',
        end: '2024-06-01',
        params: { fast: 10, slow: 30 },
      })
      setResponse(JSON.stringify(result.data, null, 2))
    } catch (err: any) {
      setError(err.message || 'Request failed')
    } finally {
      setIsLoading(false)
    }
  }

  const runMonteCarlo = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.post('/api/v1/research/montecarlo', {
        trials: 1000,
        scenario: {
          win_rate: 0.55,
          avg_win: 150,
          avg_loss: 100,
          num_trades: 100,
          initial_capital: 10000,
        },
      })
      setResponse(JSON.stringify(result.data, null, 2))
    } catch (err: any) {
      setError(err.message || 'Request failed')
    } finally {
      setIsLoading(false)
    }
  }

  const runBacktrader = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.post('/api/v1/research/backtrader', {
        strategy: 'sma-crossover',
        symbol: 'EURUSD',
        timeframe: '1h',
        start: '2024-01-01',
        end: '2024-06-01',
        params: { fast: 10, slow: 30 },
      })
      setResponse(JSON.stringify(result.data, null, 2))
    } catch (err: any) {
      setError(err.message || 'Request failed')
    } finally {
      setIsLoading(false)
    }
  }

  const tabs = [
    { key: 'backtest' as const, label: 'VectorBT Backtest', action: runBacktest },
    { key: 'montecarlo' as const, label: 'Monte Carlo', action: runMonteCarlo },
    { key: 'backtrader' as const, label: 'Backtrader', action: runBacktrader },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Research</h1>
        <p className="text-muted-foreground">Backtesting and quantitative analysis</p>
      </div>

      <div className="flex flex-wrap gap-3">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setActiveTab(t.key)
              t.action()
            }}
            disabled={isLoading}
            className={`px-4 py-2 rounded-lg border transition-colors cursor-pointer ${
              activeTab === t.key
                ? 'bg-black text-white border-black'
                : 'bg-white text-black border-gray-300 hover:bg-gray-50'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isLoading && activeTab === t.key ? 'Running…' : t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {response && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-mono">Results</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-gray-50 p-4 rounded-lg text-xs font-mono overflow-x-auto">
              {response}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
