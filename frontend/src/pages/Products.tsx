import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchProducts } from '../api'
import Pagination from '../components/Pagination'
import ProductCard from '../components/ProductCard'
import ProductCarousel from '../components/ProductCarousel'
import { pickFeatured } from '../featured'
import type { Product } from '../types'

const PAGE_SIZE = 12 // 3 rows of 4

// Category tabs use the same garment_type filter as the chat's "See all" links.
const CATEGORY_TABS = [
  { label: 'All', value: null },
  { label: 'Hoodies', value: 'hoodie' },
  { label: 'Crewnecks', value: 'crewneck' },
  { label: 'Quarter-zips', value: 'quarter-zip' },
  { label: 'Fleece & jackets', value: 'jacket' },
  { label: 'Tees', value: 't-shirt' },
]

type SortKey = 'featured' | 'price-asc' | 'price-desc' | 'name'
const SORTS: { key: SortKey; label: string }[] = [
  { key: 'featured', label: 'Featured' },
  { key: 'price-asc', label: 'Price: low to high' },
  { key: 'price-desc', label: 'Price: high to low' },
  { key: 'name', label: 'Name A–Z' },
]

const FILTER_LABELS: Record<string, (v: string) => string> = {
  q: (v) => `“${v}”`,
  garment_type: (v) => v,
  color: (v) => v,
  min_price: (v) => `from $${v}`,
  max_price: (v) => `under $${v}`,
  size: (v) => `size ${v}`,
  in_stock_only: () => 'in stock',
}

export default function Products() {
  // Filters in the URL come from the chat's "See all" link and use the agent's own search.
  const [params, setParams] = useSearchParams()
  const [products, setProducts] = useState<Product[]>([])
  const [featured, setFeatured] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('featured')
  const gridRef = useRef<HTMLDivElement>(null)

  // ?page= is for pagination only; every other URL param is a search filter for the API.
  const filterParams = new URLSearchParams(params)
  filterParams.delete('page')
  const paramKey = filterParams.toString()

  useEffect(() => {
    setLoading(true)
    setError('')
    fetchProducts(new URLSearchParams(paramKey))
      .then(setProducts)
      .catch(() => setError("We couldn't load products. Is the backend running?"))
      .finally(() => setLoading(false))
  }, [paramKey])

  // The carousel always features the same in-stock picks, whatever the filters.
  useEffect(() => {
    fetchProducts()
      .then((all) => setFeatured(pickFeatured(all)))
      .catch(() => setFeatured([]))
  }, [])

  const activeFilters = [...params.entries()].filter(([k]) => k in FILTER_LABELS)
  const activeCategory = params.get('garment_type')
  const onlyCategory = activeFilters.length === 1 && activeCategory !== null

  function chooseCategory(value: string | null) {
    const updated = new URLSearchParams()
    if (value) updated.set('garment_type', value)
    setParams(updated)
  }

  // Quick text filter over name, type, colors and tags, on top of any URL filters.
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter((p) =>
      [p.name, p.garment_type, p.description, ...p.colors, ...p.search_tags]
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [products, query])

  // In-stock pieces first under "Featured"; otherwise the shopper's chosen order.
  const sorted = useMemo(() => {
    const list = [...shown]
    if (sort === 'price-asc') list.sort((a, b) => a.price - b.price)
    else if (sort === 'price-desc') list.sort((a, b) => b.price - a.price)
    else if (sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name))
    else list.sort((a, b) => Number(b.total_stock > 0) - Number(a.total_stock > 0))
    return list
  }, [shown, sort])

  const totalPages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE))
  const page = Math.min(Math.max(1, Number(params.get('page')) || 1), totalPages)
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function goToPage(next: number) {
    const updated = new URLSearchParams(params)
    if (next === 1) updated.delete('page')
    else updated.set('page', String(next))
    setParams(updated)
    gridRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function updateQuery(text: string) {
    setQuery(text)
    if (params.has('page')) goToPage(1) // new search starts on page 1
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">The Bulldog Collection</p>
          <h1>
            {onlyCategory
              ? CATEGORY_TABS.find((c) => c.value === activeCategory)?.label ?? 'Shop'
              : activeFilters.length
                ? 'Search results'
                : 'Shop all'}
          </h1>
        </div>
        <input
          className="search"
          type="search"
          placeholder="Search hoodies, navy, baseball…"
          value={query}
          onChange={(e) => updateQuery(e.target.value)}
          aria-label="Search products"
        />
      </div>

      <div className="category-tabs" role="tablist" aria-label="Categories">
        {CATEGORY_TABS.map((c) => {
          const active = c.value === null ? activeFilters.length === 0 : onlyCategory && activeCategory === c.value
          return (
            <button key={c.label} role="tab" aria-selected={active} className={active ? 'active' : ''} onClick={() => chooseCategory(c.value)}>
              {c.label}
            </button>
          )
        })}
      </div>

      {activeFilters.length > 0 && !onlyCategory && (
        <div className="filter-bar">
          <span className="muted small">Filtered by</span>
          {activeFilters.map(([k, v]) => (
            <span key={k} className="chip">
              {FILTER_LABELS[k](v)}
            </span>
          ))}
          <Link to="/products" className="small">
            Clear filters
          </Link>
        </div>
      )}

      {activeFilters.length === 0 && !query && (
        <ProductCarousel title="Featured picks" kicker="The edit" products={featured} />
      )}

      {loading && <p className="muted">Loading products…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <>
          <div className="grid-head" ref={gridRef}>
            <div>
              <h2>{activeFilters.length || query ? 'Results' : 'All pieces'}</h2>
              <p className="muted">
                {shown.length === 0
                  ? 'No pieces match.'
                  : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, shown.length)} of ${shown.length}`}
              </p>
            </div>
            <label className="sort">
              Sort by
              <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
                {SORTS.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="product-grid four-up">
            {pageItems.map((p, i) => (
              <ProductCard key={p.product_id} product={p} index={i} />
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onChange={goToPage} />
        </>
      )}
    </div>
  )
}
