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
  // Sources
  listSources: () => apiClient.get('/kb/sources'),
  getSource: (id: string) => apiClient.get(`/kb/sources/${id}`),
  addSource: (data: { title: string; url: string; transcript?: string; tags?: string; source_type?: string }) =>
    apiClient.post('/kb/sources', data),
  deleteSource: (id: string) => apiClient.delete(`/kb/sources/${id}`),

  // Search
  search: (query: string) => apiClient.get('/kb/search', { params: { query } }),
  searchEmbeddings: (query: string, top_k: number = 5) =>
    apiClient.get('/kb/search-embeddings', { params: { query, top_k } }),

  // Transcription
  autoTranscribe: (url: string, tags?: string, use_ai_analysis?: boolean, use_whisper?: boolean) =>
    apiClient.post('/kb/auto-transcribe', { url, tags, use_ai_analysis, use_whisper }),

  // Chat
  chat: (query: string, use_vectors?: boolean, top_k?: number) =>
    apiClient.post('/kb/chat', { query, use_vectors, top_k }),

  // Status
  status: () => apiClient.get('/kb/status'),
}

// Playground API
export const playgroundApi = {
  getPrices: () => apiClient.get('/playground/prices'),
  getPrice: (symbol: string) => apiClient.get(`/playground/price/${symbol}`),
  getInstruments: () => apiClient.get('/playground/instruments'),
}

// Add interceptors here later (auth, error handling, etc.)
