import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { clearChatHistory, fetchChatHistory, fetchProduct, pageContextFor, streamChatMessage } from '../api'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import type { ChatMessage } from '../types'
import RichText from './RichText'

const GREETING: ChatMessage = {
  role: 'assistant',
  content: "Welcome aboard. I can find pieces from the collection, check live stock in your size, and help with gifts. What are you looking for today?",
}

// One-tap starter questions. On a product page they're about that item.
const GENERAL_SUGGESTIONS = ['What hoodies do you have?', 'Gift ideas for a Yale dad', 'Quarter-zips under $80', 'What’s your return policy?']
const PRODUCT_SUGGESTIONS = ['Is this in stock in M?', 'What does it look like?', 'Show me similar items']

// Floating chat panel in the bottom-right corner, backed by the PydanticAI agent.
// When a reply includes product matches, they're shown on the page (see ChatMatches).
// Signed-in shoppers' chats are saved on the server and reloaded here.
export default function ChatWidget() {
  const { user } = useAuth()
  const location = useLocation() // sent as page context, so "this" means the item on screen
  const results = useChatResults()
  const { chatOpen: open, setChatOpen: setOpen, pendingQuestion, takePendingQuestion, clear: clearResults } = results
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [viewing, setViewing] = useState<string | null>(null) // name of the product on screen
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const page = pageContextFor(location.pathname)

  // Load the saved conversation when someone signs in; start fresh when they sign out.
  useEffect(() => {
    if (!user) {
      setMessages([GREETING])
      clearResults()
      return
    }
    fetchChatHistory().then((saved) => setMessages([GREETING, ...saved]))
  }, [user, clearResults])

  // Show which item "this" refers to while on a product page.
  useEffect(() => {
    if (!page.product_id) return setViewing(null)
    fetchProduct(page.product_id)
      .then((p) => setViewing(p.name))
      .catch(() => setViewing(null))
  }, [page.product_id])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, open, sending])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  async function send(text: string) {
    text = text.trim()
    if (!text || sending) return
    const history: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setInput('')
    setSending(true)

    // Show the reply as it streams: status steps, then draft text, then the checked answer.
    let draft: ChatMessage = { role: 'assistant', content: '', draft: true, status: 'Thinking…' }
    setMessages([...history, draft])
    const update = (next: Partial<ChatMessage>) => {
      draft = { ...draft, ...next }
      setMessages([...history, draft])
    }
    // The greeting is display-only, so it isn't sent to the agent.
    const reply = await streamChatMessage(history.slice(1), page, (event) => {
      if (event.type === 'status') update({ status: event.text })
      else if (event.type === 'delta') update({ content: draft.content + event.text })
      else if (event.type === 'reset') update({ content: '', status: 'Double-checking against our inventory…' })
    })
    setMessages([...history, reply])
    setSending(false)
    if (reply.matches) results.show(reply.matches) // put the matching items on the page
  }

  // A question asked from elsewhere on the site (e.g. "Ask about this item").
  useEffect(() => {
    if (open && pendingQuestion && !sending) {
      const q = takePendingQuestion()
      if (q) send(q)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, pendingQuestion])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  async function handleClear() {
    if (user) await clearChatHistory()
    setMessages([GREETING])
    results.clear()
  }

  const suggestions = viewing ? PRODUCT_SUGGESTIONS : GENERAL_SUGGESTIONS
  const showSuggestions = !sending && messages.length <= 1

  return (
    <div className="chat">
      {open && (
        <section className="chat-panel" aria-label="Chat with the Bulldog Blue assistant">
          <header className="chat-header">
            <span className="chat-avatar" aria-hidden="true">
              CC
            </span>
            <div className="chat-title">
              <strong>Bulldog Blue Assistant</strong>
              <small>
                <span className="online-dot" aria-hidden="true" />
                {user ? `Hi, ${user.first_name} · Live inventory` : 'Answers from live inventory'}
              </small>
            </div>
            <div className="chat-header-actions">
              {messages.length > 1 && (
                <button className="chat-clear" onClick={handleClear} title="Start a new chat">
                  New chat
                </button>
              )}
              <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
                ✕
              </button>
            </div>
          </header>

          {viewing && (
            <div className="chat-context" title="The assistant knows which item you're looking at">
              <span className="chat-context-label">Now viewing</span> <strong>{viewing}</strong>
            </div>
          )}

          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-turn ${m.role}`}>
                {(m.content || !m.draft) && (
                  <div className={`chat-bubble ${m.role} ${m.draft ? 'draft' : ''}`}>
                    <RichText text={m.content} />
                  </div>
                )}
                {m.draft && m.status && (
                  <div className="chat-status" role="status">
                    <span className="typing-dots" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                    {m.status}
                  </div>
                )}
                {m.matches && (
                  <button
                    className={`chat-matches-pill ${results.matches === m.matches ? 'active' : ''}`}
                    onClick={() => results.show(m.matches!)}
                    title="Show these items on the page"
                  >
                    {results.matches === m.matches ? 'Showing ' : 'View '}
                    {m.matches.products.length} {m.matches.products.length === 1 ? 'piece' : 'pieces'} on the page
                  </button>
                )}
              </div>
            ))}
            {showSuggestions && (
              <div className="chat-suggestions" aria-label="Suggested questions">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={viewing ? 'Ask about this item…' : 'Ask about a hoodie, size, price…'}
              aria-label="Chat message"
              maxLength={1000}
            />
            <button type="submit" className="chat-send" disabled={sending || !input.trim()} aria-label="Send">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M4 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>
        </section>
      )}
      <button
        className={`chat-launcher ${open ? 'is-open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-label={open ? 'Close chat' : 'Open chat'}
        aria-expanded={open}
      >
        {open ? (
          '✕'
        ) : (
          <>
            <span className="launcher-avatar" aria-hidden="true">
              CC
            </span>
            Ask our stylist
          </>
        )}
      </button>
    </div>
  )
}
