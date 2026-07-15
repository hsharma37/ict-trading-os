import axios from 'axios'

const apiUrl = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '/api')

const API_KEY_STORAGE = 'ictos_api_key'

/** Owner-supplied API key, entered at runtime and kept only in this browser.
 *  It is never baked into the bundle or committed, per the deployment policy. */
export function getApiKey(): string {
  try {
    return localStorage.getItem(API_KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(API_KEY_STORAGE, key)
    else localStorage.removeItem(API_KEY_STORAGE)
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

export function clearApiKey(): void {
  setApiKey('')
}

export const apiClient = axios.create({
  baseURL: apiUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Attach the owner's API key to every request so production-protected routes
// (trades, plans, settings, alerts, mutations, ...) authenticate instead of 401ing.
apiClient.interceptors.request.use((config) => {
  const key = getApiKey()
  if (key) config.headers['X-Api-Key'] = key
  return config
})

// On 401, broadcast so the app can prompt for (or update) the API key.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('ictos:unauthorized'))
    }
    return Promise.reject(error)
  }
)

// KB-specific API helpers
export const kbApi = {
  listSources: () => apiClient.get('/kb/sources'),
  getSource: (id: string) => apiClient.get(`/kb/sources/${id}`),
  addSource: (data: { title: string; url: string; transcript?: string; tags?: string; source_type?: string }) =>
    apiClient.post('/kb/sources', data),
  deleteSource: (id: string) => apiClient.delete(`/kb/sources/${id}`),
  search: (query: string) => apiClient.get('/kb/search', { params: { query } }),
  searchEmbeddings: (query: string, top_k: number = 5) =>
    apiClient.get('/kb/search-embeddings', { params: { query, top_k } }),
  autoTranscribe: (url: string, tags?: string, use_ai_analysis?: boolean, use_whisper?: boolean) =>
    apiClient.post('/kb/auto-transcribe', { url, tags, use_ai_analysis, use_whisper }),
  createIngestionJob: (url: string, tags?: string, use_ai_analysis?: boolean, use_whisper?: boolean) =>
    apiClient.post('/kb/ingestion-jobs', { url, tags, use_ai_analysis, use_whisper }),
  listIngestionJobs: (limit: number = 20) =>
    apiClient.get('/kb/ingestion-jobs', { params: { limit } }),
  getIngestionJob: (id: string) => apiClient.get(`/kb/ingestion-jobs/${id}`),
  evaluateRetrieval: (top_k: number = 5) =>
    apiClient.get('/kb/eval', { params: { top_k } }),
  chat: (query: string, use_vectors?: boolean, top_k?: number) =>
    apiClient.post('/kb/chat', { query, use_vectors, top_k }),
  status: () => apiClient.get('/kb/status'),
}


// Analytics API
export const analyticsApi = {
  summary: () => apiClient.get('/analytics/summary'),
  expectancy: () => apiClient.get('/analytics/expectancy'),
  heatmap: () => apiClient.get('/analytics/heatmap'),
  drawdown: () => apiClient.get('/analytics/drawdown'),
  kelly: () => apiClient.get('/analytics/kelly'),
  symbols: () => apiClient.get('/analytics/symbols'),
  monthly: () => apiClient.get('/analytics/monthly'),
  recent: (limit = 10) => apiClient.get('/analytics/recent', { params: { limit } }),
}

// Trades & Orders API
export const tradesApi = {
  create: (data: any) => apiClient.post('/trades', data),
  list: (status?: string, symbol?: string) => apiClient.get('/trades', { params: { status, symbol } }),
  open: () => apiClient.get('/trades/open'),
  get: (id: string) => apiClient.get(`/trades/${id}`),
  partialClose: (id: string, fraction: number, exit_price: number, label?: string) =>
    apiClient.post(`/trades/${id}/partial`, { fraction, exit_price, label }),
  fullClose: (id: string, exit_price: number) =>
    apiClient.post(`/trades/${id}/close`, { exit_price }),
  moveSlToBe: (id: string) =>
    apiClient.post(`/trades/${id}/move-sl-be`),
  stats: () => apiClient.get('/trades/stats/summary'),
  kelly: () => apiClient.get('/trades/stats/kelly'),
  recent: (limit = 10) => apiClient.get('/trades/recent', { params: { limit } }),
}

export const ordersApi = {
  create: (data: any) => apiClient.post('/orders', data),
  list: (status?: string, symbol?: string) => apiClient.get('/orders', { params: { status, symbol } }),
  get: (id: string) => apiClient.get(`/orders/${id}`),
  calculateLot: (data: any) => apiClient.post('/orders/calculate-lot', data),
  quickLot: (data: any) => apiClient.post('/orders/quick-lot', data),
  execute: (id: string, exit_price: number) => apiClient.post(`/orders/${id}/execute`, { exit_price }),
  delete: (id: string) => apiClient.delete(`/orders/${id}`),
}

// Research API
export const researchApi = {
  instrument: (symbol: string) => apiClient.get(`/research/instrument/${symbol}`),
  all: () => apiClient.get('/research/all'),
  correlation: () => apiClient.get('/research/correlation'),
  summary: () => apiClient.get('/research/summary'),
  instruments: () => apiClient.get('/research/instruments'),
}

// Signals API
export const signalsApi = {
  analyze: (symbol: string) => apiClient.get(`/signals/analyze/${symbol}`),
  active: (symbol?: string) => apiClient.get('/signals/active', { params: { symbol } }),
  stats: (symbol: string) => apiClient.get(`/signals/stats/${symbol}`),
  scan: () => apiClient.post('/signals/scan'),
  intelligence: (symbol: string) => apiClient.get(`/signals/intelligence/${symbol}`),
  intelligenceAll: () => apiClient.get('/signals/intelligence'),
}

// Planner API
export const plannerApi = {
  list: (status?: string) => apiClient.get('/planner/plans', { params: { status } }),
  create: (data: any) => apiClient.post('/planner/plans', data),
  fromSignal: (signalId: string, data?: any) => apiClient.post(`/planner/from-signal/${signalId}`, data || {}),
  update: (id: string, data: any) => apiClient.post(`/planner/plans/${id}/update`, data),
  arm: (id: string) => apiClient.post(`/planner/plans/${id}/arm`),
  cancel: (id: string) => apiClient.post(`/planner/plans/${id}/cancel`),
  remove: (id: string) => apiClient.delete(`/planner/plans/${id}`),
}

// Alerts API
export const alertsApi = {
  create: (data: any) => apiClient.post('/alerts', data),
  list: (active_only?: boolean) => apiClient.get('/alerts', { params: { active_only } }),
  history: () => apiClient.get('/alerts/history'),
  delete: (id: string) => apiClient.delete(`/alerts/${id}`),
  toggle: (id: string) => apiClient.patch(`/alerts/${id}/toggle`),
  check: () => apiClient.post('/alerts/check'),
}

// Telegram API
export const telegramApi = {
  status: () => apiClient.get('/telegram/status'),
  signals: (limit: number = 50, acknowledged?: boolean, auto_traded?: boolean) =>
    apiClient.get('/telegram/signals', { params: { limit, acknowledged, auto_traded } }),
  poll: () => apiClient.post('/telegram/poll'),
  acknowledge: (id: string) => apiClient.post(`/telegram/acknowledge/${id}`),
  autoTrade: (id: string, data?: { account_balance?: number; risk_pct?: number }) =>
    apiClient.post(`/telegram/auto-trade/${id}`, data),
  stats: () => apiClient.get('/telegram/stats'),
  configure: (data: { token: string; channel_id: string }) =>
    apiClient.post('/telegram/configure', data),
}

// Market API (includes manual price override)
export const marketApi = {
  price: (symbol: string) => apiClient.get(`/market/price/${symbol}`),
  getPrice: (symbol: string) => apiClient.get(`/market/price/${symbol}`),
  getPrices: (symbols?: string) => apiClient.get('/market/prices', symbols ? { params: { symbols } } : undefined),
  history: (symbol: string, timeframe?: string) => apiClient.get(`/market/history/${symbol}`, { params: { timeframe } }),
  getHistory: (symbol: string, timeframe?: string, limit?: number) =>
    apiClient.get(`/market/history/${symbol}`, { params: { timeframe, limit } }),
  instruments: () => apiClient.get('/market/instruments'),
  getInstruments: () => apiClient.get('/market/instruments'),
  setManualPrice: (symbol: string, price: number, bid?: number, ask?: number) =>
    apiClient.post(`/market/manual-price/${symbol}`, null, { params: { price, bid, ask } }),
  clearManualPrice: (symbol: string) => apiClient.delete(`/market/manual-price/${symbol}`),
  getManualPrice: (symbol: string) => apiClient.get(`/market/manual-price/${symbol}`),
}

// MT5 API
export const mt5Api = {
  status: () => apiClient.get('/mt5/status'),
  account: () => apiClient.get('/mt5/account'),
  positions: () => apiClient.get('/mt5/positions'),
  trade: (data: { symbol: string; direction: string; lot_size: number; stop_loss?: number; take_profit?: number }) =>
    apiClient.post('/mt5/trade', null, { params: data }),
  scaledTrade: (data: { symbol: string; direction: string; lot_size: number; take_profits: string; stop_loss?: number }) =>
    apiClient.post('/mt5/scaled-trade', null, { params: data }),
  close: (ticket_id: string) => apiClient.post('/mt5/close', null, { params: { ticket_id } }),
  history: () => apiClient.get('/mt5/history'),
  // Market data
  tick: (symbol: string) => apiClient.get(`/mt5/tick/${symbol}`),
  candles: (symbol: string, timeframe = '1h', count = 200) =>
    apiClient.get(`/mt5/candles/${symbol}`, { params: { timeframe, count } }),
  symbolSpec: (symbol: string) => apiClient.get(`/mt5/symbol/${symbol}`),
  symbols: () => apiClient.get('/mt5/symbols'),
  // Order & position management
  modify: (ticket: string, stop_loss?: number, take_profit?: number) =>
    apiClient.post('/mt5/modify', null, { params: { ticket, stop_loss, take_profit } }),
  partialClose: (ticket: string, volume: number) =>
    apiClient.post('/mt5/partial-close', null, { params: { ticket, volume } }),
  pending: (data: { symbol: string; direction: string; order_kind: string; volume: number; price: number; stop_loss?: number; take_profit?: number }) =>
    apiClient.post('/mt5/pending', null, { params: data }),
  pendingOrders: () => apiClient.get('/mt5/orders'),
  cancelPending: (order_ticket: string) =>
    apiClient.post('/mt5/pending/cancel', null, { params: { order_ticket } }),
}

// Quant API
export const quantApi = {
  metrics: () => apiClient.get('/quant/metrics'),
  kelly: () => apiClient.get('/quant/kelly'),
  monteCarlo: (n_simulations?: number, n_trades?: number) =>
    apiClient.post('/quant/monte-carlo', null, { params: { n_simulations, n_trades } }),
  coach: () => apiClient.get('/quant/coach'),
  trend: (symbol: string) => apiClient.get(`/quant/trend/${symbol}`),
  volatility: (symbol: string) => apiClient.get(`/quant/volatility/${symbol}`),
  levels: (symbol: string) => apiClient.get(`/quant/levels/${symbol}`),
  session: (symbol: string) => apiClient.get(`/quant/session/${symbol}`),
  decision: (symbol: string, direction: string) =>
    apiClient.get(`/quant/decision/${symbol}`, { params: { direction } }),
}

// News API
export const newsApi = {
  latest: () => apiClient.get('/news/latest'),
  forSymbol: (symbol: string) => apiClient.get(`/news/symbol/${symbol}`),
}

// Settings API
export const settingsApi = {
  get: () => apiClient.get('/settings'),
  update: (data: any) => apiClient.post('/settings', data),
}

// Add interceptors here later (auth, error handling, etc.)
