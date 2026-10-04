import type { ChatMessage, PageContext, Product, SearchFilters, User } from './types'

// Vite proxies /api and /images to the FastAPI backend (see vite.config.ts).

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

/** Query-string form of a search, shared by the API call and the Products page URL. */
export function searchParamsFor(filters: Partial<SearchFilters>): URLSearchParams {
  const params = new URLSearchParams()
  const { query, ...rest } = filters
  if (query) params.set('q', query)
  for (const [key, value] of Object.entries(rest)) {
    if (value !== null && value !== undefined && value !== '' && value !== false) params.set(key, String(value))
  }
  return params
}

/** All products, or the same search the agent uses when filters are given. */
export function fetchProducts(params?: URLSearchParams): Promise<Product[]> {
  const qs = params?.toString()
  return getJson<Product[]>(qs ? `/api/products?${qs}` : '/api/products')
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

// ---------- Accounts ----------
// The session lives in an HttpOnly cookie set by the backend, so the browser sends it
// automatically and page scripts never see it.

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong.')
  return data as T
}

export interface SignupData {
  first_name: string
  last_name: string
  email: string
  password: string
}

export const signup = (data: SignupData) => postJson<User>('/api/auth/signup', data)
export const login = (email: string, password: string) =>
  postJson<User>('/api/auth/login', { email, password })
export const logout = () => postJson<{ ok: boolean }>('/api/auth/logout')

export async function fetchMe(): Promise<User | null> {
  const res = await fetch('/api/auth/me')
  return res.ok ? ((await res.json()) as User) : null
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`
}

// ---------- Chat ----------

/** The page context for a URL: on /products/<id>, that product is "this". */
export function pageContextFor(pathname: string): PageContext {
  const match = pathname.match(/^\/products\/([^/]+)\/?$/)
  return { path: pathname, product_id: match ? decodeURIComponent(match[1]) : null }
}

/** One line of the streaming chat response (see agent.stream_chat in the backend). */
export type ChatStreamEvent =
  | { type: 'status'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'reset' }
  | { type: 'done'; message: ChatMessage }
  | { type: 'error'; text: string }

/**
 * Streams the agent's reply (POST /api/chat/stream, one JSON event per line), calling onEvent
 * as each arrives. Resolves with the final, fact-checked message.
 */
export async function streamChatMessage(
  history: ChatMessage[],
  page: PageContext,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<ChatMessage> {
  const messages = history.slice(-50).map(({ role, content }) => ({ role, content }))
  const fail = (text: string): ChatMessage => ({ role: 'assistant', content: text })
  let res: Response
  try {
    res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, page }),
    })
  } catch {
    return fail("Sorry, I couldn't reach the assistant.")
  }
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}))
    return fail(typeof data.detail === 'string' ? data.detail : "Sorry, I couldn't reach the assistant.")
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let final: ChatMessage | null = null
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? '' // keep a partial line for the next chunk
    for (const line of lines) {
      if (!line.trim()) continue
      const event = JSON.parse(line) as ChatStreamEvent
      onEvent(event)
      if (event.type === 'done') final = event.message
      if (event.type === 'error') final = fail(event.text)
    }
  }
  return final ?? fail('Sorry, the answer was cut off. Please try again.')
}

/** The signed-in shopper's saved chat ([] when signed out). */
export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const res = await fetch('/api/chat/history')
  return res.ok ? ((await res.json()) as ChatMessage[]) : []
}

export async function clearChatHistory(): Promise<void> {
  await fetch('/api/chat/history', { method: 'DELETE' })
}
