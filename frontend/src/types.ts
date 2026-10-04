export interface SizeStock {
  size: string
  quantity: number
}

// ---------- Chat → page contract (mirrors backend/models.py) ----------

/** ProductCard: one product card on the website. */
export interface MatchCard {
  product_id: string
  name: string
  garment_type: string
  price: number
  colors: string[]
  image_url: string
  total_stock: number
  sizes_in_stock: string[]
  short_description: string
}

/** SearchFilters: the agent's search behind the cards, reused by "See all". */
export interface SearchFilters {
  query: string
  garment_type: string | null
  color: string | null
  min_price: number | null
  max_price: number | null
  size: string | null
  in_stock_only: boolean
}

/** ProductMatches: the structured matches for one chat reply. */
export interface ProductMatches {
  title: string
  search: SearchFilters | null
  total_found: number | null
  products: MatchCard[]
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  price: number
  image_url: string
  total_stock: number
  sizes?: SizeStock[] // only on the single-product endpoint
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  matches?: ProductMatches | null // product cards the agent wants shown on the page
  draft?: boolean // still streaming; not yet fact-checked
  status?: string // what the agent is doing right now, e.g. "Checking live stock…"
}

/** PageContext: where the shopper is when they send a chat message (mirrors backend/models.py). */
export interface PageContext {
  path: string
  product_id: string | null
}

export interface User {
  id: number
  first_name: string
  last_name: string
  email: string
}
