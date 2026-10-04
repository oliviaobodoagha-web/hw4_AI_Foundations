import { useRef, type PointerEvent, type ReactNode } from 'react'

// A sideways "shop the look" row: swipe on touch, drag with the mouse, or use the arrows.
// Scroll-snap lands each card neatly at the left edge.
export default function LookbookRow({ children }: { children: ReactNode }) {
  const track = useRef<HTMLDivElement>(null)
  const drag = useRef({ active: false, startX: 0, startScroll: 0, moved: false })

  const step = (dir: 1 | -1) => {
    const el = track.current
    if (!el) return
    const card = el.firstElementChild as HTMLElement | null
    el.scrollBy({ left: dir * ((card?.offsetWidth ?? 300) + 18), behavior: 'smooth' })
  }

  // Mouse drag (touch already swipes natively).
  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' || !track.current) return
    drag.current = { active: true, startX: e.clientX, startScroll: track.current.scrollLeft, moved: false }
    track.current.classList.add('dragging')
  }
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (!d.active || !track.current) return
    const dx = e.clientX - d.startX
    if (Math.abs(dx) > 4) d.moved = true
    track.current.scrollLeft = d.startScroll - dx
  }
  const onUp = () => {
    drag.current.active = false
    track.current?.classList.remove('dragging')
  }
  // A drag shouldn't also count as a click on the card underneath.
  const onClickCapture = (e: React.MouseEvent) => {
    if (drag.current.moved) {
      e.preventDefault()
      e.stopPropagation()
      drag.current.moved = false
    }
  }

  return (
    <div className="lookbook-row">
      <div className="lookbook-arrows">
        <button onClick={() => step(-1)} aria-label="Previous looks">
          ‹
        </button>
        <button onClick={() => step(1)} aria-label="Next looks">
          ›
        </button>
      </div>
      <div
        ref={track}
        className="model-track"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        onClickCapture={onClickCapture}
      >
        {children}
      </div>
    </div>
  )
}
