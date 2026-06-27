import { useState, useEffect } from 'react'

export function useMarketData(symbol: string) {
  const [price, setPrice] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiUrl}/api/v1/market/price/${symbol}`)
        if (!res.ok) throw new Error('Failed to fetch price')
        const data = await res.json()
        setPrice(data.price)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchPrice()
    const interval = setInterval(fetchPrice, 30000) // Poll every 30s
    return () => clearInterval(interval)
  }, [symbol])

  return { price, loading, error }
}
