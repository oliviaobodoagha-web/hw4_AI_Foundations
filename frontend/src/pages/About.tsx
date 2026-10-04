import { Link } from 'react-router-dom'
import PhotoCredit from '../components/PhotoCredit'
import { PHOTOS, photoUrl } from '../lifestyle'

export default function About() {
  return (
    <>
    <section className="page-banner">
      <div className="banner-bg" data-parallax="0.15" style={{ backgroundImage: `url(${photoUrl(PHOTOS.sunset, 2000, 900)})` }} />
      <div className="banner-text">
        <p className="eyebrow">About Us</p>
        <h1>
          Made for the Bulldog <em>in all of us.</em>
        </h1>
      </div>
      <PhotoCredit photo={PHOTOS.sunset} />
    </section>
    <div className="page narrow">

      <p className="lead">
        Bulldog Blue is the Yale shop run by Campus Customs. We started with a simple idea: school
        spirit gear should feel as good as it looks, and it should be easy to find something that
        fits your story, whether you're a student, a graduate, or the person who drove them up
        I-95 on move-in day.
      </p>

      <h2>What we make</h2>
      <p>
        Everything we sell is officially licensed Yale merchandise: hoodies, crewnecks, tees,
        quarter-zips and jackets for game days, late-night study sessions and everything in
        between. You'll find gear for Yale's teams, the residential colleges, the graduate and
        professional schools, and class years, plus plenty for proud parents and family.
      </p>

      <h2>Where to find us</h2>
      <p>
        Our home base is <strong>57 Broadway in New Haven, CT</strong>, right in the middle of
        campus life. Can't stop by? We ship across the U.S. and internationally.
      </p>

      <h2>The details that matter</h2>
      <ul className="facts">
        <li>
          <strong>Turnaround:</strong> most orders are made within about 5–8 business days, then
          ship (usually with UPS) with tracking.
        </li>
        <li>
          <strong>Returns:</strong> changed your mind? Send back unworn items with tags on within
          30 days of shipping. Custom and personalized pieces are final sale.
        </li>
        <li>
          <strong>International orders:</strong> any customs duties or import taxes are paid by
          the buyer.
        </li>
        <li>
          <strong>Questions?</strong> Our chat assistant (bottom-right) can help with products,
          prices and stock. For orders, reach the Campus Customs team at
          orderdept@campuscustoms.com or (475) 301-4205.
        </li>
      </ul>

      <div className="about-cta">
        <Link to="/products" className="btn btn-primary">
          Start shopping
        </Link>
      </div>
    </div>
    </>
  )
}
