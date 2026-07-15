import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mt5Api } from '@/api/client'

export interface Mt5Position {
  ticket: string
  symbol: string
  direction: 'long' | 'short'
  lot_size: number
  open_price: number
  current_price?: number
  sl: number
  tp: number
  profit: number
  swap: number
}

export interface Mt5Account {
  balance: number
  equity: number
  margin: number
  free_margin: number
  margin_level: number
  currency?: string
  status?: string
}

/**
 * Single shared source of live MT5 state for the whole app. Because every
 * caller uses the same React Query keys, Dashboard, What's Up and the MT5
 * Terminal all read one deduped, auto-refreshing cache — so positions and P&L
 * are identical everywhere — and the close/modify/partial mutations invalidate
 * that one cache, so an action taken on any page updates all of them.
 */
export function useMt5() {
  const qc = useQueryClient()

  // Gentle intervals: the bridge is reached over a single tunnel, so keep the
  // request rate modest. React Query dedupes across all pages using these keys.
  const status = useQuery({
    queryKey: ['mt5', 'status'],
    queryFn: () => mt5Api.status().then((r) => r.data),
    refetchInterval: 20000,
  })
  const account = useQuery({
    queryKey: ['mt5', 'account'],
    queryFn: () => mt5Api.account().then((r) => r.data as Mt5Account),
    refetchInterval: 15000,
  })
  const positions = useQuery({
    queryKey: ['mt5', 'positions'],
    queryFn: () => mt5Api.positions().then((r) => (r.data?.positions || []) as Mt5Position[]),
    refetchInterval: 8000,
  })
  const history = useQuery({
    queryKey: ['mt5', 'history'],
    queryFn: () => mt5Api.history().then((r) => r.data?.history || []),
    refetchInterval: 60000,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['mt5'] })

  const close = useMutation({
    mutationFn: (ticket: string) => mt5Api.close(ticket),
    onSuccess: invalidate,
  })
  const modify = useMutation({
    mutationFn: (v: { ticket: string; stop_loss?: number; take_profit?: number }) =>
      mt5Api.modify(v.ticket, v.stop_loss, v.take_profit),
    onSuccess: invalidate,
  })
  const partialClose = useMutation({
    mutationFn: (v: { ticket: string; volume: number }) => mt5Api.partialClose(v.ticket, v.volume),
    onSuccess: invalidate,
  })

  const positionsData = positions.data || []

  // Freshness: when did we last get a good positions read, and is it stale?
  // Orders should be gated on live, fresh connectivity — not a cached "connected"
  // from a minute ago while the tunnel is actually down.
  const lastUpdated = positions.dataUpdatedAt || 0
  const stale = !!lastUpdated && Date.now() - lastUpdated > 30000

  return {
    connected: !!status.data?.reachable && !!(status.data?.bridge_response?.mt5_connected),
    reachable: !!status.data?.reachable,
    account: account.data,
    positions: positionsData,
    history: (history.data || []) as any[],
    totalProfit: positionsData.reduce((s, p) => s + (p.profit || 0), 0),
    loading: positions.isLoading,
    lastUpdated,
    stale,
    error: (positions.error as any)?.response?.data?.detail || (status.error as any)?.message || null,
    refetch: invalidate,
    close,
    modify,
    partialClose,
  }
}
