import axios from 'axios'

// Workaround for import.meta.env type issues in strict TS
const _env = (globalThis as any)?.import?.meta?.env ?? {};
const apiUrl = _env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: apiUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

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
  chat: (query: string, use_vectors?: boolean, top_k?: number) =>
    apiClient.post('/kb/chat', { query, use_vectors, top_k }),
  status: () => apiClient.get('/kb/status'),
}

// Add interceptors here later (auth, error handling, etc.)
export const playgroundApi = {
  getPrices: () => apiClient.get('/playground/prices'),
  getPrice: (symbol: string) => apiClient.get(`/playground/price/${symbol}`),
  getInstruments: () => apiClient.get('/playground/instruments'),
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

// Market API
export const marketApi = {
  price: (symbol: string) => apiClient.get(`/market/price/${symbol}`),
  history: (symbol: string, timeframe?: string) => apiClient.get(`/market/history/${symbol}`, { params: { timeframe } }),
  instruments: () => apiClient.get('/market/instruments'),
}

// MT5 API
export const mt5Api = {
  status: () => apiClient.get('/mt5/status'),
  account: () => apiClient.get('/mt5/account'),
  positions: () => apiClient.get('/mt5/positions'),
  trade: (data: any) => apiClient.post('/mt5/trade', data),
  close: (data: any) => apiClient.post('/mt5/close', data),
  history: () => apiClient.get('/mt5/history'),
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

// Add interceptors here later (auth, error handling, etc.)