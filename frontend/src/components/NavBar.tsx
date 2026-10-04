import { useEffect, useState } from 'react'
import { useReducedMotion } from '../motion'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const ANNOUNCEMENTS = [
  'Officially licensed Yale apparel',
  'Made in New Haven, Connecticut',
  '30-day returns on unworn pieces',
]

const LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Shop' },
  { to: '/about', label: 'About Us' },
]

// Heritage-store header: shop links on the left, the centered serif wordmark, account on the right.
export default function NavBar() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const reduced = useReducedMotion()
  const [scrolled, setScrolled] = useState(false) // past the top: header slims down
  const [hidden, setHidden] = useState(false) // scrolling down: header tucks away
  const [notice, setNotice] = useState(0)

  // Slim on scroll, hide while scrolling down, slide back in as soon as you scroll up.
  useEffect(() => {
    let last = window.scrollY
    const onScroll = () => {
      const y = window.scrollY
      setScrolled(y > 40)
      if (Math.abs(y - last) > 6) {
        setHidden(y > last && y > 260)
        last = y
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // The announcement bar rotates through its messages.
  useEffect(() => {
    if (reduced) return
    const t = window.setInterval(() => setNotice((n) => (n + 1) % ANNOUNCEMENTS.length), 4000)
    return () => window.clearInterval(t)
  }, [reduced])

  async function handleLogout() {
    close()
    await logout()
    navigate('/')
  }

  return (
    <header className={`site-header ${scrolled ? 'is-scrolled' : ''} ${hidden && !open ? 'is-hidden' : ''}`}>
      <div className="announcement" aria-live="polite">
        <span className="announcement-dot" aria-hidden="true">✦</span>
        <span key={notice} className="announcement-text">
          {ANNOUNCEMENTS[notice]}
        </span>
        <span className="announcement-dot" aria-hidden="true">✦</span>
      </div>
      <nav className="navbar">
        <button
          className="nav-toggle"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <span />
          <span />
          <span />
        </button>

        <div className={`nav-links nav-left ${open ? 'open' : ''}`}>
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} onClick={close}>
              {l.label}
            </NavLink>
          ))}
          {/* account links repeat inside the mobile menu */}
          <div className="nav-mobile-account">
            {user ? (
              <button className="nav-text-btn" onClick={handleLogout}>
                Log Out
              </button>
            ) : (
              <>
                <NavLink to="/login" onClick={close}>
                  Log In
                </NavLink>
                <NavLink to="/create-account" onClick={close}>
                  Create Account
                </NavLink>
              </>
            )}
          </div>
        </div>

        <Link to="/" className="brand" onClick={close} aria-label="Bulldog Blue by Campus Customs, home">
          <span className="brand-name">Bulldog Blue</span>
          <span className="brand-sub">by Campus Customs · New Haven</span>
        </Link>

        <div className="nav-links nav-right">
          {loading ? null : user ? (
            <>
              <span className="nav-user">Hello, {user.first_name}</span>
              <button className="nav-text-btn" onClick={handleLogout}>
                Log Out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log In</NavLink>
              <NavLink to="/create-account" className="nav-cta">
                Create Account
              </NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  )
}
