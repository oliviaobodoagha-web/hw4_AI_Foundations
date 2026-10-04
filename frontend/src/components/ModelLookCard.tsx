import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { modelPhotoUrl, type ModelLook } from '../lifestyle'
import type { Product } from '../types'

// A model photo with our product's real print laid onto the garment, plus a "shop it" caption.
export default function ModelLookCard({ look, product, index = 0 }: { look: ModelLook; product?: Product; index?: number }) {
  const p = look.print
  return (
    <figure className="model-look" data-reveal style={{ '--i': index } as CSSProperties}>
      <Link to={`/products/${look.productId}`} className="model-frame" aria-label={product ? `Shop ${product.name}` : 'Shop this piece'}>
        <span className="model-inner">
          <img className="model-photo" src={modelPhotoUrl(look)} alt={look.photo.alt} loading="lazy" />
          <img
          className="model-print"
          src={`/images/prints/${look.productId}.png`}
          alt=""
          aria-hidden="true"
          style={{
            left: `${p.left}%`,
            top: `${p.top}%`,
            width: `${p.width}%`,
            transform: `rotate(${p.rotate}deg)`,
            mixBlendMode: p.blend,
            opacity: p.opacity,
          }}
          />
        </span>
        <span className="model-setting">{look.setting}</span>
      </Link>
      <figcaption>
        <span className="model-wearing">Wearing</span>
        <Link to={`/products/${look.productId}`}>{product?.name ?? 'This piece'}</Link>
        {product && <span className="model-price">{formatPrice(product.price)}</span>}
        <a className="model-credit" href={look.photo.page} target="_blank" rel="noreferrer">
          Photo: {look.photo.credit} / Unsplash · print added digitally
        </a>
      </figcaption>
    </figure>
  )
}
