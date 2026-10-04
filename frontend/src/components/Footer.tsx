import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="stripe" aria-hidden="true" />
      <div className="footer-inner">
        <div className="footer-brand">
          <span className="brand-name">Bulldog Blue</span>
          <p>Officially licensed Yale apparel by Campus Customs.</p>
          <p>57 Broadway, New Haven, CT 06511</p>
        </div>
        <div className="footer-col">
          <h4>Shop</h4>
          <Link to="/products?garment_type=hoodie">Hoodies</Link>
          <Link to="/products?garment_type=crewneck">Crewnecks</Link>
          <Link to="/products?garment_type=quarter-zip">Quarter-zips</Link>
          <Link to="/products?garment_type=t-shirt">Tees</Link>
        </div>
        <div className="footer-col">
          <h4>Service</h4>
          <Link to="/about">Shipping &amp; returns</Link>
          <Link to="/about">About us</Link>
          <a href="mailto:orderdept@campuscustoms.com">orderdept@campuscustoms.com</a>
          <span>(475) 301-4205</span>
        </div>
        <div className="footer-col">
          <h4>Account</h4>
          <Link to="/login">Log in</Link>
          <Link to="/create-account">Create account</Link>
        </div>
      </div>
      <p className="footer-note">
        A student class project inspired by yalebulldogblue.com. Not the official store.
      </p>
    </footer>
  )
}
