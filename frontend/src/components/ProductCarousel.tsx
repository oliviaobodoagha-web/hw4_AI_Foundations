import { useEffect, useState } from 'react'
import ProductCard from './ProductCard'
import type { Product } from '../types'

// How many cards fit side by side: 3 on desktop (as requested), fewer on small screens.
function useCardsPerView(): number {
  const get = () => (window.innerWidth < 600 ? 1 : window.innerWidth < 900 ? 2 : 3)
  const [perView, setPerView] = useState(get)
  useEffect(() => {
    const onResize = () => setPerView(get())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return perView
}

// Shows products 3 at a time with arrows and dots, so shoppers see items without scrolling.
export default function ProductCarousel({
  title,
  kicker,
  products,
}: {
  title: string
  kicker?: string
  products: Product[]
}) {
  const perView = useCardsPerView()
  const pages = Math.max(1, Math.ceil(products.length / perView))
  const [page, setPage] = useState(0)

  useEffect(() => setPage((p) => Math.min(p, pages - 1)), [pages])
  if (products.length === 0) return null

  const go = (next: number) => setPage((next + pages) % pages) // wraps around at the ends

  return (
    <section className="carousel" aria-roledescription="carousel" aria-label={title}>
      <div className="carousel-head">
        <div>
          {kicker && <p className="eyebrow">{kicker}</p>}
          <h2>{title}</h2>
        </div>
        <div className="carousel-arrows">
          <button onClick={() => go(page - 1)} aria-label="Previous products">
            ‹
          </button>
          <button onClick={() => go(page + 1)} aria-label="Next products">
            ›
          </button>
        </div>
      </div>
      <div className="carousel-window">
        <div
          className="carousel-track"
          style={{ transform: `translateX(-${page * 100}%)`, ['--per-view' as string]: perView }}
        >
          {products.map((p, i) => (
            <div
              className="carousel-slide"
              key={p.product_id}
              aria-hidden={Math.floor(i / perView) !== page}
            >
              <ProductCard product={p} />
            </div>
          ))}
        </div>
      </div>
      <div className="carousel-dots">
        {Array.from({ length: pages }, (_, i) => (
          <button
            key={i}
            className={i === page ? 'active' : ''}
            onClick={() => setPage(i)}
            aria-label={`Show products ${i * perView + 1}–${Math.min((i + 1) * perView, products.length)}`}
          />
        ))}
      </div>
    </section>
  )
}
