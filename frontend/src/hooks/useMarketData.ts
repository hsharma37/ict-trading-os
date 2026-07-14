import { useState, useEffect } from 'react'
import { apiClient } from '@/api/client'

export function useMarketData(symbol: string) {
  const [price, setPrice] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const fetchPrice = async () => {
      try {
        // Use the shared apiClient (not raw fetch) so requests carry the
        // X-Api-Key header and any 401 triggers the global API-key banner.
        const { data } = await apiClient.get(`/market/price/${symbol}`)
        if (!cancelled) setPrice(data.price)
      } catch (err: any) {
        if (!cancelled) setError(err?.response?.data?.detail || err?.message || 'Unknown error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchPrice()
    const interval = setInterval(fetchPrice, 30000) // Poll every 30s
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [symbol])

  return { price, loading, error }
}
