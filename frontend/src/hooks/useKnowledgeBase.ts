import { useState, useCallback, useEffect } from 'react'
import { kbApi } from '@/api/client'

export interface KBSource {
  id: string
  title: string
  url: string
  source_type: string
  transcript?: string
  tags?: string[]
  concepts?: string[]
  analysis?: {
    summary?: string
    key_concepts?: string[]
    timestamps?: Array<{ time: string; concept: string; description: string }>
    ict_relevance?: string
    trading_insights?: string
    sentiment?: string
    word_count?: number
    ai_enhanced?: boolean
    transcript_source?: string
    actionable_takeaways?: string[]
  }
  metadata?: {
    video_id?: string
    channel?: string
    duration?: number
    view_count?: number
    upload_date?: string
  }
  chunk_count?: number
  created_at?: string
}

export interface TranscribeResult {
  created: Array<{
    id: string
    title: string
    url: string
    transcript_added: boolean
    analysis?: any
  }>
  failed: Array<{ url: string; title: string; error: string }>
  source_count: number
  channel_analysis?: {
    videos_analyzed: number
    total_words: number
    top_concepts: Array<[string, number]>
    sentiment_distribution: Record<string, number>
    dominant_sentiment: string
  }
  url_type: string
}

export function useKnowledgeBase() {
  const [sources, setSources] = useState<KBSource[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [lastResult, setLastResult] = useState<TranscribeResult | null>(null)
  const [status, setStatus] = useState<any>(null)

  const fetchSources = useCallback(async () => {
    try {
      const response = await kbApi.listSources()
      setSources(response.data || [])
    } catch (e) {
      console.error('Failed to fetch sources:', e)
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const response = await kbApi.status()
      setStatus(response.data)
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }, [])

  useEffect(() => {
    fetchSources()
    fetchStatus()
  }, [fetchSources, fetchStatus])

  const addSource = useCallback(async (title: string, url: string, transcript: string, tags: string) => {
    setIsLoading(true)
    try {
      await kbApi.addSource({ title, url, transcript, tags, source_type: 'manual' })
      await fetchSources()
      await fetchStatus()
    } catch (e: any) {
      console.error('Add source failed:', e)
      alert(e?.response?.data?.detail || 'Failed to add source')
    } finally {
      setIsLoading(false)
    }
  }, [fetchSources, fetchStatus])

  const autoTranscribe = useCallback(async (url: string, tags: string, useAI: boolean = true) => {
    setIsTranscribing(true)
    try {
      const response = await kbApi.autoTranscribe(url, tags, useAI, true)
      setLastResult(response.data)
      await fetchSources()
      await fetchStatus()
      return response.data
    } catch (e: any) {
      console.error('Transcription failed:', e)
      const errorMsg = e?.response?.data?.detail || e?.message || 'Transcription failed'
      alert(errorMsg)
      return null
    } finally {
      setIsTranscribing(false)
    }
  }, [fetchSources, fetchStatus])

  const deleteSource = useCallback(async (id: string) => {
    try {
      await kbApi.deleteSource(id)
      await fetchSources()
      await fetchStatus()
    } catch (e) {
      console.error('Delete failed:', e)
    }
  }, [fetchSources, fetchStatus])

  return {
    sources,
    status,
    isLoading,
    isTranscribing,
    lastResult,
    addSource,
    autoTranscribe,
    deleteSource,
    refresh: fetchSources,
  }
}
