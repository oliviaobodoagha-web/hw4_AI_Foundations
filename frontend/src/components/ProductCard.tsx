import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { MODEL_LOOKS, modelPhotoUrl } from '../lifestyle'
import { swatchFor } from '../swatches'

const SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
const LOOK_BY_PRODUCT = new Map(MODEL_LOOKS.map((l) => [l.productId, l]))

// Works for catalogue products (full description) and chat matches (short_description + sizes).
interface CardProduct {
  product_id: string
  name: string
  price: number
  image_url: string
  total_stock: number
  garment_type?: string
  colors?: string[]
  description?: string
  short_description?: string
  sizes_in_stock?: string[]
  sizes?: { size: string; quantity: number }[]
}

// Shorten long descriptions for the grid; the full text is on the product page.
function shorten(text: string, max = 90): string {
  return text.length <= max ? text : text.slice(0, text.lastIndexOf(' ', max)) + '…'
}

export default function ProductCard({
  product,
  onOpen,
  index = 0,
}: {
  product: CardProduct
  onOpen?: () => void
  index?: number // stagger position when cards cascade in
}) {
  const soldOut = product.total_stock === 0
  const fewSizes = !soldOut && product.sizes_in_stock !== undefined && product.sizes_in_stock.length <= 3
  const info = product.short_description ?? shorten(product.description ?? '')
  const look = LOOK_BY_PRODUCT.get(product.product_id) // on hover, show it worn by a model
  const inStock = new Set(product.sizes ? product.sizes.filter((s) => s.quantity > 0).map((s) => s.size) : product.sizes_in_stock)
  return (
    // Every card (catalogue or chat match) opens the same single-item page.
    <Link
      to={`/products/${product.product_id}`}
      className={`product-card ${look ? 'has-look' : ''}`}
      onClick={onOpen}
      data-reveal
      style={{ '--i': index % 4 } as CSSProperties}
    >
      <div className="product-card-img">
        <img className="card-main" src={product.image_url} alt={product.name} loading="lazy" />
        {look && (
          <span className="card-alt" aria-hidden="true">
            <img src={modelPhotoUrl(look)} alt="" loading="lazy" />
            <img
              className="model-print"
              src={`/images/prints/${look.productId}.png`}
              alt=""
              style={{
                left: `${look.print.left}%`,
                top: `${look.print.top}%`,
                width: `${look.print.width}%`,
                transform: `rotate(${look.print.rotate}deg)`,
                mixBlendMode: look.print.blend,
                opacity: look.print.opacity,
              }}
            />
          </span>
        )}
        {soldOut && <span className="badge">Sold out</span>}
        {fewSizes && <span className="badge badge-light">Limited sizes</span>}
        <span className="card-view" aria-hidden="true">
          {!soldOut && inStock.size > 0 && (
            <span className="card-quick-sizes">
              {SIZE_ORDER.map((s) => (
                <span key={s} className={inStock.has(s) ? '' : 'out'}>
                  {s}
                </span>
              ))}
            </span>
          )}
          View details
        </span>
      </div>
      <div className="product-card-body">
        {product.garment_type && <p className="card-type">{product.garment_type}</p>}
        <h3>{product.name}</h3>
        <p className="price">{formatPrice(product.price)}</p>
        {product.colors && product.colors.length > 0 && (
          <div className="swatches" aria-label={`Colors: ${product.colors.join(', ')}`}>
            {product.colors.slice(0, 5).map((c) => (
              <span key={c} className="swatch" style={{ background: swatchFor(c) }} title={c} />
            ))}
          </div>
        )}
        <p className="short-desc">{info}</p>
        {product.sizes_in_stock && !soldOut && <p className="card-sizes">{product.sizes_in_stock.join(' · ')}</p>}
      </div>
    </Link>
  )
}
