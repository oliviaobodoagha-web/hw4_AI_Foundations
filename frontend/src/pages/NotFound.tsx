import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="page narrow">
      <h1>Page not found</h1>
      <p>
        That page wandered off campus. <Link to="/">Head home</Link> or{' '}
        <Link to="/products">browse products</Link>.
      </p>
    </div>
  )
}
