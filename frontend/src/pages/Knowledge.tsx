import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { AIChatPanel } from '@/components/AIChatPanel'

export default function Knowledge() {
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [transcript, setTranscript] = useState('')
  const [isIngesting, setIsIngesting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)

  const handleAddSource = async () => {
    if (!youtubeUrl && !transcript) return

    setIsIngesting(true)
    try {
      // TODO: Call API to ingest
      console.log('Ingesting:', { youtubeUrl, transcript })
    } catch (error) {
      console.error('Ingestion failed:', error)
    } finally {
      setIsIngesting(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return

    setIsSearching(true)
    try {
      // TODO: Call API to search
      console.log('Searching:', searchQuery)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
        <p className="text-muted-foreground">ICT transcripts, notes, and AI chat</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">YouTube URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Paste YouTube link..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="flex-1 px-3 py-2 border rounded-md bg-background"
                />
                <Button onClick={handleAddSource} disabled={isIngesting}>
                  {isIngesting ? 'Adding...' : 'Add'}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Or paste transcript text</label>
              <textarea
                className="w-full px-3 py-2 border rounded-md bg-background min-h-[100px]"
                placeholder="Paste transcript here..."
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
              />
              <Button onClick={handleAddSource} disabled={isIngesting} className="w-full">
                {isIngesting ? 'Adding...' : 'Add to Knowledge Base'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Chat</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="h-[400px]">
              <AIChatPanel />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search your knowledge base..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 px-3 py-2 border rounded-md bg-background"
            />
            <Button onClick={handleSearch} disabled={isSearching}>
              {isSearching ? 'Searching...' : 'Search'}
            </Button>
          </div>
          <div className="mt-4">
            {searchResults.length > 0 ? (
              <div className="space-y-2">
                {searchResults.map((result: any, index: number) => (
                  <div key={index} className="p-3 border rounded-md bg-muted">
                    <div className="text-sm font-medium">{result.title}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Similarity: {result.similarity?.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                Search results will appear here
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
