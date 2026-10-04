import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from './api'
import type { User } from './types'

interface AuthState {
  user: User | null
  loading: boolean // true until we've asked the backend who's logged in
  login: (email: string, password: string) => Promise<void>
  signup: (data: api.SignupData) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

// Holds the signed-in shopper for the whole app. On load it asks /api/auth/me,
// so a refresh keeps you logged in as long as the session cookie is valid.
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.fetchMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  const value: AuthState = {
    user,
    loading,
    login: async (email, password) => setUser(await api.login(email, password)),
    signup: async (data) => setUser(await api.signup(data)),
    logout: async () => {
      await api.logout()
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
