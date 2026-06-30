import { useState } from 'react'
import { Send, Bot, User, Loader2, Trash2, ExternalLink, BookOpen, Hash, Sparkles } from 'lucide-react'
import { useAIChat } from '@/hooks/useAIChat'

interface Source {
  id: string
  title: string
  url: string
  score: number
}

export function AIChatPanel() {
  const [input, setInput] = useState('')
  const { messages, isLoading, sendMessage, clearChat, messagesEndRef } = useAIChat()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    await sendMessage(input)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full border rounded-lg bg-card">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">AI Knowledge Assistant</h3>
        </div>
        <button
          onClick={clearChat}
          className="p-2 text-muted-foreground hover:text-destructive rounded-md hover:bg-muted"
          title="Clear chat"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">Ask me anything about your knowledge base</p>
            <p className="text-sm mt-2">Try: "What is a fair value gap?" or "Explain order blocks"</p>
            <p className="text-xs mt-4 opacity-70">
              First ingest some YouTube videos or transcripts, then ask questions!
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-3 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}

            <div className="max-w-[85%] space-y-2">
              <div
                className={`rounded-lg p-3 ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
              </div>

              {/* Sources Panel for assistant messages */}
              {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <BookOpen className="w-3.5 h-3.5" />
                    Sources Used
                  </div>
                  <div className="space-y-1.5">
                    {message.sources.map((source: Source) => (
                      <div key={source.id} className="flex items-center justify-between gap-2 text-xs">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline truncate"
                        >
                          <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate">{source.title}</span>
                        </a>
                        <div className="flex items-center gap-1 text-muted-foreground flex-shrink-0">
                          <Sparkles className="w-3 h-3" />
                          <span className="font-mono">{(source.score * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Key Concepts Panel for assistant messages */}
              {message.role === 'assistant' && message.key_concepts && message.key_concepts.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground uppercase mr-1">
                    <Hash className="w-3 h-3" />
                    Key concepts:
                  </div>
                  {message.key_concepts.map((concept: string, idx: number) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-[10px] border border-primary/10"
                    >
                      {concept}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {message.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
            </div>
            <div className="bg-muted rounded-lg p-3">
              <div className="text-sm text-muted-foreground">Searching knowledge base...</div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about ICT concepts, setups, or your knowledge base..."
            className="flex-1 px-3 py-2 border rounded-md bg-background text-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  )
}
