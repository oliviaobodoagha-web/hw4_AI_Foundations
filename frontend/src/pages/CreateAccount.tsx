import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function CreateAccount() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/" replace />

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value })

  const mismatch = form.confirm.length > 0 && form.confirm !== form.password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (form.password.length < 8) return setError('Password must be at least 8 characters.')
    if (form.password !== form.confirm) return setError("Passwords don't match.")
    setSubmitting(true)
    try {
      const { confirm: _confirm, ...data } = form // confirm is only checked here, never sent
      await signup(data)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
      setSubmitting(false)
    }
  }

  return (
    <div className="page auth">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Join the Bulldog Blue crew</h1>
        <p className="muted">Create an account to save your chats with our assistant.</p>
        <div className="row">
          <label>
            First name
            <input autoComplete="given-name" value={form.first_name} onChange={update('first_name')} required />
          </label>
          <label>
            Last name
            <input autoComplete="family-name" value={form.last_name} onChange={update('last_name')} required />
          </label>
        </div>
        <label>
          Email
          <input type="email" autoComplete="email" value={form.email} onChange={update('email')} required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={form.password}
            onChange={update('password')}
            required
          />
          <span className="hint">At least 8 characters.</span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            value={form.confirm}
            onChange={update('confirm')}
            aria-invalid={mismatch}
            required
          />
          {mismatch && <span className="hint bad">Passwords don't match yet.</span>}
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" className="btn btn-primary full" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
        <p className="muted small">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
