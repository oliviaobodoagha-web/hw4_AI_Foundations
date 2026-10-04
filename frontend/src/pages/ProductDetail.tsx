import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice } from '../api'
import { useChatResults } from '../chatResults'
import { swatchFor } from '../swatches'
import type { Product } from '../types'

function stockLabel(qty: number): string {
  if (qty === 0) return 'Sold out'
  if (qty <= 3) return `Only ${qty} left`
  return 'In stock'
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  const { ask } = useChatResults()
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    setProduct(null)
    setError('')
    setSelected(null)
    fetchProduct(productId)
      .then(setProduct)
      .catch(() => setError("We couldn't find that product."))
  }, [productId])

  if (error)
    return (
      <div className="page">
        <p className="error">{error}</p>
        <Link to="/products">← Back to the collection</Link>
      </div>
    )
  if (!product) return <div className="page muted">Loading…</div>

  const sizes = product.sizes ?? []
  const chosen = sizes.find((s) => s.size === selected)

  return (
    <div className="page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Home</Link>
        <span aria-hidden="true">/</span>
        <Link to="/products">Shop</Link>
        <span aria-hidden="true">/</span>
        <span>{product.name}</span>
      </nav>
      <div className="detail">
        <div className="detail-img">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div className="detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p className="detail-desc">{product.description}</p>

          <div className="detail-block">
            <h3>Colorway</h3>
            <div className="swatch-list">
              {product.colors.map((c) => (
                <span key={c} className="swatch-named">
                  <span className="swatch" style={{ background: swatchFor(c) }} />
                  {c}
                </span>
              ))}
            </div>
          </div>

          <div className="detail-block">
            <h3>
              Size{' '}
              <span className="size-hint">
                {chosen
                  ? `${chosen.size}: ${stockLabel(chosen.quantity)} (${chosen.quantity} available)`
                  : product.total_stock === 0
                    ? 'Sold out in every size'
                    : 'Select a size'}
              </span>
            </h3>
            <div className="sizes">
              {sizes.map((s) => (
                <button
                  key={s.size}
                  className={`size ${s.quantity === 0 ? 'out' : ''} ${s.quantity > 0 && s.quantity <= 3 ? 'low' : ''} ${selected === s.size ? 'selected' : ''}`}
                  disabled={s.quantity === 0}
                  onClick={() => setSelected(s.size)}
                  title={stockLabel(s.quantity)}
                >
                  {s.size}
                </button>
              ))}
            </div>
            <table className="stock-table">
              <tbody>
                {sizes.map((s) => (
                  <tr key={s.size}>
                    <td>{s.size}</td>
                    <td className={s.quantity === 0 ? 'out' : s.quantity <= 3 ? 'low' : ''}>{stockLabel(s.quantity)}</td>
                    <td className="qty">{s.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            className="btn btn-outline full"
            onClick={() => ask(chosen ? `Is this available in ${chosen.size}, and how does it fit?` : 'Tell me more about this piece.')}
          >
            Ask our stylist about this piece
          </button>

          <ul className="trust-list">
            <li>Officially licensed Yale apparel</li>
            <li>Made in about 5–8 business days, then shipped with tracking</li>
            <li>30-day returns on unworn pieces with tags</li>
          </ul>

          <div className="detail-block">
            <h3>Details</h3>
            <div className="chips">
              {product.search_tags.map((t) => (
                <span key={t} className="chip subtle">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
