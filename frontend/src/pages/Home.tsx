import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, formatPrice } from '../api'
import HeroSlideshow from '../components/HeroSlideshow'
import LookbookRow from '../components/LookbookRow'
import ModelLookCard from '../components/ModelLookCard'
import PhotoCredit from '../components/PhotoCredit'
import ProductCarousel from '../components/ProductCarousel'
import { pickFeatured } from '../featured'
import { MODEL_LOOKS, PHOTOS, photoUrl, type Photo } from '../lifestyle'
import type { Product } from '../types'

// Shop-by-category tiles: each links to the same search the chat's "See all" uses.
const CATEGORIES = [
  { label: 'Hoodies', filter: 'hoodie', image: 'basic-hoodie-big-yale' },
  { label: 'Crewnecks', filter: 'crewneck', image: 'baseball-left-chest-crewneck' },
  { label: 'Quarter-zips', filter: 'quarter-zip', image: 'branford-1-4-zip' },
  { label: 'Fleece & jackets', filter: 'jacket', image: 'divinity-school-fleece-sweater' },
  { label: 'Tees', filter: 't-shirt', image: '2025-yale-vs-harvard-t-shirt' },
]

// Lookbook: a real Yale / New England photo paired with a real piece from the catalogue.
const LOOKS: { kicker: string; title: string; photo: Photo; productId: string; link: string }[] = [
  { kicker: 'On campus', title: 'Between lectures on Old Campus', photo: PHOTOS.harkness, productId: 'basic-hoodie-big-yale', link: '/products?garment_type=hoodie' },
  { kicker: 'Out in the world', title: 'A long weekend on the water', photo: PHOTOS.sails, productId: 'benjamin-franklin-1-4-zip', link: '/products?garment_type=quarter-zip' },
]

// Hero photos that crossfade, starting with the original lawn shot.
const HERO_SLIDES: Photo[] = [PHOTOS.lawn, PHOTOS.harkness, PHOTOS.sails, PHOTOS.autumn, PHOTOS.harbor]

const SEASONS: { label: string; photo: Photo }[] = [
  { label: 'First snow', photo: PHOTOS.gate },
  { label: 'Harbor season', photo: PHOTOS.harbor },
  { label: 'Fall in New Haven', photo: PHOTOS.autumn },
]

export default function Home() {
  const [all, setAll] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts()
      .then(setAll)
      .catch(() => setAll([]))
  }, [])

  const byId = new Map(all.map((p) => [p.product_id, p]))
  const featured = pickFeatured(all)

  return (
    <>
      <section className="hero">
        <HeroSlideshow photos={HERO_SLIDES} />
        <div className="hero-inner">
          <div className="hero-copy">
            <p className="eyebrow">The Bulldog Collection · New Haven</p>
            <h1>
              Classic Yale, <em>made to be lived in.</em>
            </h1>
            <p className="hero-sub">Heritage crewnecks, quarter-zips and hoodies, from the quad to the dock.</p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-light">
                Shop the collection
              </Link>
              <Link to="/about" className="btn btn-link light">
                Our story
              </Link>
            </div>
          </div>
        </div>
      </section>
      <div className="stripe" aria-hidden="true" />

      <section className="section carousel-section">
        {featured.length > 0 ? (
          <ProductCarousel title="Fan favorites" kicker="The edit" products={featured} />
        ) : (
          <p className="muted">Start the backend to load products.</p>
        )}
      </section>

      <section className="section models" aria-label="Worn by Bulldogs">
        <div className="section-title" data-reveal>
          <p className="eyebrow">The lookbook</p>
          <h2>
            Worn by Bulldogs, <em>everywhere.</em>
          </h2>
        </div>
        <LookbookRow>
          {MODEL_LOOKS.map((look, i) => (
            <ModelLookCard key={look.productId} look={look} product={byId.get(look.productId)} index={i} />
          ))}
        </LookbookRow>
      </section>

      <section className="section lookbook" aria-label="Lookbook">
        {LOOKS.map((look, i) => {
          const product = byId.get(look.productId)
          return (
            <article key={look.kicker} className="look" data-reveal style={{ '--i': i } as CSSProperties}>
              <img className="look-photo" src={photoUrl(look.photo, 1100, 1300)} alt={look.photo.alt} loading="lazy" data-parallax="0.08" />
              <div className="look-text">
                <p className="eyebrow">{look.kicker}</p>
                <h2>{look.title}</h2>
                <Link to={look.link} className="btn-link light">
                  Shop the look
                </Link>
              </div>
              {product && (
                <Link to={`/products/${product.product_id}`} className="look-product">
                  <img src={product.image_url} alt={product.name} />
                  <span>
                    <strong>{product.name}</strong>
                    {formatPrice(product.price)}
                  </span>
                </Link>
              )}
              <PhotoCredit photo={look.photo} />
            </article>
          )
        })}
      </section>

      <section className="section categories">
        <div className="section-title" data-reveal>
          <p className="eyebrow">Shop by category</p>
          <h2>Something for every season</h2>
        </div>
        <div className="category-grid">
          {CATEGORIES.map((c, i) => {
            const img = byId.get(c.image)?.image_url
            return (
              <Link key={c.label} to={`/products?garment_type=${c.filter}`} className="category-tile" data-reveal style={{ '--i': i } as CSSProperties}>
                <div className="category-img">{img && <img src={img} alt="" loading="lazy" />}</div>
                <span>{c.label}</span>
              </Link>
            )
          })}
        </div>
      </section>

      <section className="seasons" aria-label="New England seasons">
        {SEASONS.map((s, i) => (
          <figure key={s.label} className="season" data-reveal style={{ '--i': i } as CSSProperties}>
            <img src={photoUrl(s.photo, 900, 700)} alt={s.photo.alt} loading="lazy" data-parallax="0.1" />
            <figcaption>{s.label}</figcaption>
            <PhotoCredit photo={s.photo} />
          </figure>
        ))}
      </section>

      <section className="value-strip" data-reveal>
        <div>
          <strong>Officially licensed</strong>
          <span>Authentic Yale marks, done properly</span>
        </div>
        <div>
          <strong>Made in New Haven</strong>
          <span>Printed and shipped from 57 Broadway</span>
        </div>
        <div>
          <strong>A stylist on hand</strong>
          <span>Honest answers on sizing and live stock</span>
        </div>
      </section>

      <section className="section split-callout" data-reveal>
        <div className="callout-bg" data-parallax="0.12" style={{ backgroundImage: `url(${photoUrl(PHOTOS.lighthouse, 1600, 900)})` }} />
        <div>
          <p className="eyebrow">For the whole family</p>
          <h2>
            Gifts for the <em>proudest</em> Yale parents.
          </h2>
          <p>
            From a quarter-zip for Family Weekend to a crewneck for the newest Bulldog, our stylist
            can help you find something they'll wear for years.
          </p>
          <Link to="/products" className="btn btn-light">
            Find a gift
          </Link>
        </div>
        <PhotoCredit photo={PHOTOS.lighthouse} />
      </section>
    </>
  )
}
