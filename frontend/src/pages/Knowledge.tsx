import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { AIChatPanel } from '@/components/AIChatPanel'
import { useKnowledgeBase } from '@/hooks/useKnowledgeBase'
import {
  Youtube, FileText, Trash2, Search, Loader2, BookOpen,
  Tag, Clock, Eye, BarChart3, Brain, CheckCircle, AlertCircle,
  ChevronDown, ChevronUp, ExternalLink
} from 'lucide-react'

export default function Knowledge() {
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [transcriptText, setTranscriptText] = useState('')
  const [tags, setTags] = useState('')
  const [manualTitle, setManualTitle] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [useAI, setUseAI] = useState(true)

  const {
    sources, status, isLoading, isTranscribing, lastResult,
    addSource, autoTranscribe, deleteSource, refresh
  } = useKnowledgeBase()

  const handleAddSource = async () => {
    if (!manualTitle || !transcriptText) return
    await addSource(manualTitle, 'manual-entry', transcriptText, tags)
    setManualTitle('')
    setTranscriptText('')
  }

  const handleAutoTranscribe = async () => {
    if (!youtubeUrl.trim()) return
    await autoTranscribe(youtubeUrl.trim(), tags, useAI)
    setYoutubeUrl('')
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setIsSearching(true)
    try {
      const { kbApi } = await import('@/api/client')
      const response = await kbApi.searchEmbeddings(searchQuery, 8)
      setSearchResults(response.data || [])
    } catch (e) {
      console.error('Search failed:', e)
      // Fallback to text search
      try {
        const { kbApi } = await import('@/api/client')
        const response = await kbApi.search(searchQuery)
        const results = (response.data || []).map((s: any) => ({
          source_title: s.title,
          source_url: s.url,
          chunk_text: s.transcript?.substring(0, 300) || '',
          score: 1.0,
        }))
        setSearchResults(results)
      } catch (e2) {
        console.error('Fallback search failed:', e2)
      }
    } finally {
      setIsSearching(false)
    }
  }

  const formatDuration = (seconds: number) => {
    if (!seconds) return 'N/A'
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}m ${s}s`
  }

  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return 'N/A'
    try {
      return new Date(dateStr).toLocaleDateString()
    } catch {
      return dateStr
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
        <p className="text-muted-foreground">
          Ingest YouTube videos, transcripts, and chat with your ICT knowledge base
          {status && (
            <span className="ml-2 text-xs">
              ({status.source_count} sources, {status.chunk_count} chunks, {status.youtube_source_count} videos)
            </span>
          )}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Left Column: Ingestion & Sources */}
        <div className="space-y-4">
          {/* YouTube Auto-Transcribe */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Youtube className="w-5 h-5 text-red-500" />
                YouTube Auto-Transcribe
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">YouTube URL (video, playlist, or channel)</label>
                <input
                  type="text"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Tags (comma-separated)</label>
                <input
                  type="text"
                  placeholder="ICT, FVG, liquidity, ..."
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="useAI"
                  checked={useAI}
                  onChange={(e) => setUseAI(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <label htmlFor="useAI" className="text-sm flex items-center gap-1">
                  <Brain className="w-4 h-4" />
                  Use AI Analysis (LLM-powered summary & insights)
                </label>
              </div>
              <Button
                onClick={handleAutoTranscribe}
                disabled={isTranscribing || !youtubeUrl.trim()}
                className="w-full"
              >
                {isTranscribing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Transcribing & Analyzing...
                  </>
                ) : (
                  <>
                    <Youtube className="w-4 h-4 mr-2" />
                    Auto-Transcribe & Ingest
                  </>
                )}
              </Button>

              {/* Last result summary */}
              {lastResult && (
                <div className="mt-3 p-3 bg-muted rounded-md text-sm space-y-2">
                  <div className="flex items-center gap-2 font-medium">
                    {lastResult.failed.length === 0 ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-yellow-500" />
                    )}
                    {lastResult.url_type === 'channel' ? 'Channel' : lastResult.url_type === 'playlist' ? 'Playlist' : 'Video'} analyzed
                    ({lastResult.source_count} sources created)
                  </div>
                  {lastResult.channel_analysis && (
                    <div className="text-xs space-y-1">
                      <div>Videos: {lastResult.channel_analysis.videos_analyzed} | Words: {lastResult.channel_analysis.total_words}</div>
                      <div>Sentiment: {lastResult.channel_analysis.dominant_sentiment}</div>
                      <div>Top concepts: {lastResult.channel_analysis.top_concepts.slice(0, 5).map((c: any) => c[0]).join(', ')}</div>
                    </div>
                  )}
                  {lastResult.failed.length > 0 && (
                    <div className="text-xs text-red-500">
                      {lastResult.failed.length} failed: {lastResult.failed.map((f: any) => f.title).join(', ')}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Manual Entry */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Manual Transcript Entry
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <input
                type="text"
                placeholder="Title"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
              <textarea
                className="w-full px-3 py-2 border rounded-md bg-background min-h-[100px] text-sm"
                placeholder="Paste transcript or notes here..."
                value={transcriptText}
                onChange={(e) => setTranscriptText(e.target.value)}
              />
              <Button
                onClick={handleAddSource}
                disabled={isLoading || !manualTitle || !transcriptText}
                variant="outline"
                className="w-full"
              >
                {isLoading ? 'Adding...' : 'Add to Knowledge Base'}
              </Button>
            </CardContent>
          </Card>

          {/* Search */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="w-5 h-5" />
                Search Knowledge Base
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Search concepts, setups, transcripts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="flex-1 px-3 py-2 border rounded-md bg-background text-sm"
                />
                <Button onClick={handleSearch} disabled={isSearching || !searchQuery.trim()}>
                  {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </Button>
              </div>
              {searchResults.length > 0 && (
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {searchResults.map((result: any, index: number) => (
                    <div key={index} className="p-3 border rounded-md bg-muted/50">
                      <div className="text-sm font-medium flex items-center gap-1">
                        <BookOpen className="w-3 h-3" />
                        {result.source_title || 'Unknown'}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1 line-clamp-3">
                        {result.chunk_text || result.transcript?.substring(0, 200)}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Relevance: {result.score?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: AI Chat */}
        <div>
          <Card className="h-[600px] flex flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                AI Knowledge Chat
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 p-0 overflow-hidden">
              <AIChatPanel />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Sources List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <BookOpen className="w-5 h-5" />
              Sources ({sources.length})
            </span>
            <Button variant="ghost" size="sm" onClick={refresh}>
              Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {sources.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              No sources yet. Add a YouTube URL or paste a transcript to get started.
            </div>
          ) : (
            <div className="space-y-3">
              {sources.map((source) => {
                const isExpanded = expandedSource === source.id
                const analysis = source.analysis || {}
                const metadata = source.metadata || {}

                return (
                  <div key={source.id} className="border rounded-md overflow-hidden">
                    <div
                      className="p-3 flex items-center justify-between cursor-pointer hover:bg-muted/50"
                      onClick={() => setExpandedSource(isExpanded ? null : source.id)}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {source.source_type === 'youtube' ? (
                          <Youtube className="w-4 h-4 text-red-500 flex-shrink-0" />
                        ) : (
                          <FileText className="w-4 h-4 flex-shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{source.title}</div>
                          <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                            {source.source_type === 'youtube' && (
                              <>
                                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDuration(metadata.duration || 0)}</span>
                                <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{(metadata.view_count || 0).toLocaleString()}</span>
                                <span>{metadata.channel}</span>
                              </>
                            )}
                            {source.chunk_count !== undefined && (
                              <span>{source.chunk_count} chunks</span>
                            )}
                            {analysis.ict_relevance && (
                              <span className={`px-1.5 py-0.5 rounded text-xs ${
                                analysis.ict_relevance === 'high' ? 'bg-green-100 text-green-700' :
                                analysis.ict_relevance === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {analysis.ict_relevance} relevance
                              </span>
                            )}
                            {analysis.sentiment && (
                              <span className={`px-1.5 py-0.5 rounded text-xs ${
                                analysis.sentiment === 'bullish' ? 'bg-green-100 text-green-700' :
                                analysis.sentiment === 'bearish' ? 'bg-red-100 text-red-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {analysis.sentiment}
                              </span>
                            )}
                            {analysis.ai_enhanced && (
                              <span className="flex items-center gap-1 text-xs text-primary">
                                <Brain className="w-3 h-3" /> AI
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteSource(source.id)
                          }}
                          className="p-1 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="p-3 border-t bg-muted/30 space-y-3">
                        {/* Analysis */}
                        {analysis.summary && (
                          <div>
                            <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">Summary</div>
                            <div className="text-sm">{analysis.summary}</div>
                          </div>
                        )}

                        {/* Key Concepts */}
                        {analysis.key_concepts && analysis.key_concepts.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">Key Concepts</div>
                            <div className="flex flex-wrap gap-1">
                              {analysis.key_concepts.map((concept: string) => (
                                <span key={concept} className="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs">
                                  {concept}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Timestamps */}
                        {analysis.timestamps && analysis.timestamps.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">Key Timestamps</div>
                            <div className="space-y-1">
                              {analysis.timestamps.slice(0, 5).map((ts: any, idx: number) => (
                                <div key={idx} className="text-xs flex items-start gap-2">
                                  <span className="font-mono bg-muted px-1 rounded">{ts.time}</span>
                                  <span className="text-muted-foreground">{ts.concept}: {ts.description?.substring(0, 100)}...</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Trading Insights */}
                        {analysis.trading_insights && (
                          <div>
                            <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">Trading Insights</div>
                            <div className="text-sm text-muted-foreground">{analysis.trading_insights}</div>
                          </div>
                        )}

                        {/* Actionable Takeaways */}
                        {analysis.actionable_takeaways && analysis.actionable_takeaways.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">Actionable Takeaways</div>
                            <ul className="list-disc list-inside text-sm space-y-1">
                              {analysis.actionable_takeaways.slice(0, 5).map((item: string, idx: number) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Tags & Concepts */}
                        <div className="flex flex-wrap gap-1">
                          {source.tags?.map((tag: string) => (
                            <span key={tag} className="px-2 py-0.5 bg-muted rounded-full text-xs flex items-center gap-1">
                              <Tag className="w-3 h-3" />{tag}
                            </span>
                          ))}
                          {source.concepts?.map((concept: string) => (
                            <span key={concept} className="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs">
                              {concept}
                            </span>
                          ))}
                        </div>

                        {/* Link */}
                        {source.url && source.url !== 'manual-entry' && (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-primary flex items-center gap-1 hover:underline"
                          >
                            <ExternalLink className="w-3 h-3" /> Open on YouTube
                          </a>
                        )}

                        {/* Stats */}
                        <div className="text-xs text-muted-foreground flex items-center gap-3">
                          <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" />{analysis.word_count || 0} words</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDate(source.created_at)}</span>
                          {analysis.transcript_source && (
                            <span>Source: {analysis.transcript_source}</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
