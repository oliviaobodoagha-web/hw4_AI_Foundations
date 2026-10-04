// Page motion in the spirit of J.Crew: elements ease in as they scroll into view, and big
// lifestyle images drift slightly slower than the page (parallax). Everything is opt-in with
// data attributes, so any component can use it:
//   data-reveal              fade + rise when it enters the screen
//   style={{'--i': n}}       stagger index: the nth item waits n × 70ms
//   data-parallax="0.12"     drift factor (fraction of the distance from screen center)
// Shoppers whose device asks for reduced motion see everything immediately and still.

import { useEffect, useState } from 'react'

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

/** Watches the whole page (including content that loads later) for [data-reveal] elements. */
export function useScrollReveal(): void {
  useEffect(() => {
    const reveal = (el: Element) => el.classList.add('is-revealed')
    const pending = () => document.querySelectorAll('[data-reveal]:not(.is-revealed)')
    if (prefersReducedMotion()) {
      const showAll = () => pending().forEach(reveal)
      showAll()
      const mo = new MutationObserver(showAll)
      mo.observe(document.body, { childList: true, subtree: true })
      return () => mo.disconnect()
    }

    // Reveal anything whose top has entered the lower 92% of the screen (or that's already above it).
    let frame = 0
    const check = () => {
      frame = 0
      const limit = window.innerHeight * 0.92
      pending().forEach((el) => {
        if (el.getBoundingClientRect().top < limit) reveal(el)
      })
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(check)
    }
    check()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    const mo = new MutationObserver(schedule) // products and photos that load later
    mo.observe(document.body, { childList: true, subtree: true })
    // Safety net: never leave content hidden, even if scroll events are missed.
    const safety = window.setInterval(check, 1000)
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      mo.disconnect()
      window.clearInterval(safety)
      cancelAnimationFrame(frame)
    }
  }, [])
}

/** Moves [data-parallax] elements a little as the page scrolls, for a layered, editorial depth. */
export function useParallax(): void {
  useEffect(() => {
    if (prefersReducedMotion()) return
    let frame = 0
    const update = () => {
      frame = 0
      const mid = window.innerHeight / 2
      document.querySelectorAll<HTMLElement>('[data-parallax]').forEach((el) => {
        const box = (el.parentElement ?? el).getBoundingClientRect()
        if (box.bottom < -200 || box.top > window.innerHeight + 200) return // off screen
        const factor = Number(el.dataset.parallax) || 0.1
        const offset = (box.top + box.height / 2 - mid) * factor
        el.style.setProperty('--parallax', `${(-offset).toFixed(1)}px`)
      })
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    const mo = new MutationObserver(onScroll)
    mo.observe(document.body, { childList: true, subtree: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      mo.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [])
}
