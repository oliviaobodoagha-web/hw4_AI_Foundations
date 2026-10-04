import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import type { ProductMatches } from './types'

interface ChatResultsState {
  matches: ProductMatches | null // the cards currently shown on the page
  show: (matches: ProductMatches) => void
  clear: () => void
  // Opening the chat from elsewhere on the page (e.g. "Ask about this item").
  chatOpen: boolean
  setChatOpen: (open: boolean) => void
  pendingQuestion: string | null // a question to send as soon as the chat opens
  ask: (question: string) => void
  takePendingQuestion: () => string | null
}

const ChatResultsContext = createContext<ChatResultsState | null>(null)

// Shares the agent's latest product matches between the chat widget (which receives
// them) and the page (which renders them as product cards), and lets any page open the
// chat with a question.
export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [matches, setMatches] = useState<ProductMatches | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const clear = useCallback(() => setMatches(null), [])
  const ask = useCallback((question: string) => {
    setPendingQuestion(question)
    setChatOpen(true)
  }, [])
  const takePendingQuestion = useCallback(() => {
    const q = pendingQuestion
    setPendingQuestion(null)
    return q
  }, [pendingQuestion])
  return (
    <ChatResultsContext.Provider
      value={{ matches, show: setMatches, clear, chatOpen, setChatOpen, pendingQuestion, ask, takePendingQuestion }}
    >
      {children}
    </ChatResultsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChatResults(): ChatResultsState {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
