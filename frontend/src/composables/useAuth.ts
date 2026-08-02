import { ref, computed } from 'vue'

/**
 * Auth state management for PolicyIQ.
 * Stores JWT in localStorage, exposes reactive user state.
 * Design: docs/10-AUTH-AND-ACCOUNTS.md, docs/13-COMPETITIVE-STRATEGY.md §5.
 */

const TOKEN_KEY = 'policyiq-token'

export interface AuthUser {
  id: string
  email: string
  name: string | null
  role: string
  subscription_active: boolean
  credit_balance: number
  created_at: string
}

const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
const user = ref<AuthUser | null>(null)

export const isAuthenticated = computed(() => !!token.value)

export function useAuth() {
  function setToken(t: string) {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
  }

  function clearToken() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  function getToken(): string | null {
    return token.value
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
      const res = await fetch(`${BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (res.ok) {
        user.value = await res.json()
      } else {
        clearToken()
      }
    } catch {
      clearToken()
    }
  }

  function logout() {
    clearToken()
  }

  // Auto-fetch user on init if token exists
  if (token.value) {
    fetchUser()
  }

  return { token, user, isAuthenticated, setToken, clearToken, getToken, fetchUser, logout }
}
