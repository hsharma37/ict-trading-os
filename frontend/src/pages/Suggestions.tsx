import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { apiClient } from '@/api/client'

interface SuggestionItem {
  id: string
  symbol: string
  direction: string
  setup_type: string
  setup_score: number
  confluence_score: number
  confidence: number
  suggested_entry: number | null
  suggested_stop: number | null
  suggested_target: number | null
  suggested_lot_size: number | null
  risk_amount: number | null
  expected_r: number | null
  ai_narrative: string | null
  status: string
  paper_trade: boolean
  created_at: string
}

export default function Suggestions() {
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)

  const userId = '00000000-0000-0000-0000-000000000000'

  async function load() {
    try {
      const res = await apiClient.get(`/api/v1/suggestions/pending?user_id=${userId}`)
      setSuggestions(res.data || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load suggestions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleApprove(id: string) {
    setActionInProgress(id)
    try {
      await apiClient.post(`/api/v1/suggestions/${id}/approve`)
      await load()
    } catch (err: any) {
      setError(err.message || 'Approval failed')
    } finally {
      setActionInProgress(null)
    }
  }

  async function handleExecute(id: string) {
    setActionInProgress(id)
    try {
      await apiClient.post(`/api/v1/suggestions/${id}/execute`)
      await load()
    } catch (err: any) {
      setError(err.message || 'Execution failed')
    } finally {
      setActionInProgress(null)
    }
  }

  async function handleReject(id: string) {
    setActionInProgress(id)
    try {
      await apiClient.post(`/api/v1/suggestions/${id}/reject?reason=User rejected`)
      await load()
    } catch (err: any) {
      setError(err.message || 'Rejection failed')
    } finally {
      setActionInProgress(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Signals</h1>
        <p>Loading...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Signals</h1>
        <p className="text-muted-foreground">AI and rule-based trade suggestions awaiting approval</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {suggestions.filter((s) => s.status === 'pending').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Approved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {suggestions.filter((s) => s.status === 'approved').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Executed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {suggestions.filter((s) => s.status === 'executed').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Paper Trades</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {suggestions.filter((s) => s.paper_trade).length}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4">
        {suggestions.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No pending suggestions. Signals will appear here when AI or rules generate them.
            </CardContent>
          </Card>
        ) : (
          suggestions.map((s) => (
            <Card key={s.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle>
                    {s.symbol} {s.direction.toUpperCase()}
                    {s.paper_trade && (
                      <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">
                        Paper
                      </span>
                    )}
                  </CardTitle>
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      s.status === 'pending'
                        ? 'bg-yellow-100 text-yellow-800'
                        : s.status === 'approved'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {s.status}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Setup</span>
                    <span className="font-medium">{s.setup_type || 'N/A'} (score: {s.setup_score})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Confluence</span>
                    <span className="font-medium">{s.confluence_score}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Confidence</span>
                    <span className="font-medium">{(s.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Entry</span>
                    <span className="font-medium">{s.suggested_entry?.toFixed(5) ?? 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Stop</span>
                    <span className="font-medium">{s.suggested_stop?.toFixed(5) ?? 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Target</span>
                    <span className="font-medium">{s.suggested_target?.toFixed(5) ?? 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Risk</span>
                    <span className="font-medium">${s.risk_amount?.toFixed(2) ?? 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Expected R</span>
                    <span className="font-medium">{s.expected_r?.toFixed(2) ?? 'N/A'}</span>
                  </div>
                  {s.ai_narrative && (
                    <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-muted-foreground">
                      {s.ai_narrative}
                    </div>
                  )}
                </div>

                <div className="flex gap-2 mt-4">
                  {s.status === 'pending' && (
                    <>
                      <button
                        onClick={() => handleApprove(s.id)}
                        disabled={actionInProgress === s.id}
                        className="px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
                      >
                        {actionInProgress === s.id ? '...' : 'Approve'}
                      </button>
                      <button
                        onClick={() => handleReject(s.id)}
                        disabled={actionInProgress === s.id}
                        className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {s.status === 'approved' && (
                    <button
                      onClick={() => handleExecute(s.id)}
                      disabled={actionInProgress === s.id}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                    >
                      {actionInProgress === s.id ? '...' : 'Execute Trade'}
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
