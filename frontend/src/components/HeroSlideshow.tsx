import { useEffect, useState, type CSSProperties } from 'react'
import { photoUrl, type Photo } from '../lifestyle'
import { useReducedMotion } from '../motion'

const SLIDE_MS = 4600 // how long each scene plays before the next fades in

// A living hero: lifestyle photos crossfade every few seconds with a slow zoom (Ken Burns),
// the way a fashion homepage feels like moving footage. Still for reduced-motion shoppers.
export default function HeroSlideshow({ photos }: { photos: Photo[] }) {
  const reduced = useReducedMotion()
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (reduced || photos.length < 2) return
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % photos.length), SLIDE_MS)
    return () => window.clearInterval(timer)
  }, [reduced, photos.length])

  const current = photos[index]
  return (
    <>
      {/* The slides layer drifts slower than the page as you scroll (parallax). */}
      <div className="hero-slides" aria-hidden="true" data-parallax="0.25">
        {photos.map((p, i) => (
          <div
            key={p.id}
            // Each scene gets its own camera move (pan left, pan right, push in, ...) like footage.
            className={`hero-slide move-${i % 4} ${i === index ? 'active' : ''}`}
            style={{ backgroundImage: `url(${photoUrl(p, 2200, 1000)})` }}
          />
        ))}
      </div>
      {photos.length > 1 && (
        <div className="hero-dots">
          {photos.map((p, i) => (
            <button
              key={`${p.id}-${i === index ? index : 'idle'}`}
              className={i === index ? 'active' : ''}
              style={{ '--slide-ms': `${SLIDE_MS}ms` } as CSSProperties}
              onClick={() => setIndex(i)}
              aria-label={`Show photo ${i + 1}: ${p.alt}`}
            />
          ))}
        </div>
      )}
      <a className="photo-credit" href={current.page} target="_blank" rel="noreferrer">
        Photo: {current.credit} / Unsplash
      </a>
    </>
  )
}
