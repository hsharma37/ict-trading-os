import { useState, useRef, useCallback } from 'react'
import { kbApi } from '@/api/client'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{
    id: string
    title: string
    url: string
    score: number
  }>
}

export function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = useCallback(async (input: string) => {
    if (!input.trim()) return

    const userMessage: ChatMessage = { role: 'user', content: input.trim() }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await kbApi.chat(userMessage.content, true, 5)
      const data = response.data

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.answer || 'No answer generated.',
        sources: data.sources || [],
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error: any) {
      console.error('Chat error:', error)
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${error?.response?.data?.detail || error.message || 'Failed to get answer'}`,
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
      setTimeout(scrollToBottom, 100)
    }
  }, [])

  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, isLoading, sendMessage, clearChat, messagesEndRef }
}
