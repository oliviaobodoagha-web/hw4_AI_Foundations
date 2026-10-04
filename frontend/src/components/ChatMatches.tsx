import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { searchParamsFor } from '../api'
import { useChatResults } from '../chatResults'
import ProductCard from './ProductCard'

// The page side of the chat contract: renders the agent's product matches as cards
// at the top of whatever page the shopper is on.
export default function ChatMatches() {
  const { matches, clear } = useChatResults()
  const ref = useRef<HTMLElement>(null)
  const [collapsed, setCollapsed] = useState(false)

  // New matches open the panel and come into view.
  useEffect(() => {
    if (!matches) return
    setCollapsed(false)
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [matches])

  if (!matches) return null

  // Opening a card shows the single-item page; shrink the panel so that page is fully visible.
  function openCard() {
    setCollapsed(true)
    window.scrollTo({ top: 0 })
  }

  if (collapsed)
    return (
      <section className="chat-matches collapsed" ref={ref} aria-label="Products from chat">
        <span>
          <strong>{matches.title}</strong> · {matches.products.length} from your conversation
        </span>
        <div className="chat-matches-actions">
          <button className="btn-text strong" onClick={() => setCollapsed(false)}>
            Show
          </button>
          <button className="btn-text" onClick={clear} aria-label="Hide chat matches">
            ✕
          </button>
        </div>
      </section>
    )
  const shown = matches.products.length
  const total = matches.total_found ?? shown
  const seeAll = matches.search ? `/products?${searchParamsFor(matches.search)}` : null

  return (
    <section className="chat-matches" ref={ref} aria-live="polite" aria-label="Products from chat">
      <div className="chat-matches-head">
        <div>
          <p className="eyebrow">From your conversation</p>
          <h2>{matches.title}</h2>
          <p className="muted small">
            {total > shown ? `Showing ${shown} of ${total} matches` : `${shown} ${shown === 1 ? 'match' : 'matches'}`}
          </p>
        </div>
        <div className="chat-matches-actions">
          {seeAll && total > shown && (
            <Link to={seeAll} className="btn btn-primary small-btn" onClick={clear}>
              See all {total}
            </Link>
          )}
          <button className="btn-text" onClick={clear} aria-label="Hide chat matches">
            Hide ✕
          </button>
        </div>
      </div>
      <div className="product-grid">
        {matches.products.map((p, i) => (
          <ProductCard key={p.product_id} product={p} onOpen={openCard} index={i} />
        ))}
      </div>
    </section>
  )
}
