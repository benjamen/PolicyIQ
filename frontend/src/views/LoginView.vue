<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { setToken, fetchUser } = useAuth()

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const name = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const endpoint = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const body: Record<string, string> = { email: email.value, password: password.value }
    if (mode.value === 'register' && name.value) body.name = name.value

    const res = await fetch(`${BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (!res.ok) {
      error.value = data.detail || `Request failed (${res.status})`
      return
    }
    setToken(data.access_token)
    await fetchUser()
    router.push('/account')
  } catch (e) {
    error.value = 'Network error — is the API running?'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-sm mx-auto mt-16">
    <div class="text-center mb-8">
      <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-teal to-[#084c3e] dark:from-teal-dark dark:to-[#0f5c4b] flex items-center justify-center mx-auto mb-4 shadow-md">
        <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      </div>
      <h1 class="text-xl font-bold">{{ mode === 'login' ? 'Sign in' : 'Create account' }}</h1>
      <p class="text-sm text-slate dark:text-slate-dark mt-1">
        {{ mode === 'login' ? 'Access your PolicyIQ account' : 'Start comparing NZ insurance policies' }}
      </p>
    </div>

    <form @submit.prevent="submit" class="space-y-4">
      <div v-if="mode === 'register'">
        <label class="block text-xs font-medium mb-1.5 text-slate dark:text-slate-dark">Name (optional)</label>
        <input
          v-model="name"
          type="text"
          class="w-full px-3 py-2 rounded-lg border border-black/10 dark:border-white/15 bg-white dark:bg-white/5 text-sm focus:outline-none focus:ring-2 focus:ring-teal/40"
          placeholder="Your name"
        />
      </div>
      <div>
        <label class="block text-xs font-medium mb-1.5 text-slate dark:text-slate-dark">Email</label>
        <input
          v-model="email"
          type="email"
          required
          class="w-full px-3 py-2 rounded-lg border border-black/10 dark:border-white/15 bg-white dark:bg-white/5 text-sm focus:outline-none focus:ring-2 focus:ring-teal/40"
          placeholder="you@company.co.nz"
        />
      </div>
      <div>
        <label class="block text-xs font-medium mb-1.5 text-slate dark:text-slate-dark">Password</label>
        <input
          v-model="password"
          type="password"
          required
          minlength="8"
          class="w-full px-3 py-2 rounded-lg border border-black/10 dark:border-white/15 bg-white dark:bg-white/5 text-sm focus:outline-none focus:ring-2 focus:ring-teal/40"
          placeholder="Min 8 characters"
        />
      </div>

      <p v-if="error" class="text-xs text-brick dark:text-brick bg-brick/10 dark:bg-brick/20 px-3 py-2 rounded-lg">{{ error }}</p>

      <button
        type="submit"
        :disabled="loading"
        class="w-full py-2.5 rounded-lg bg-teal dark:bg-teal-dark text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
      >
        {{ loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account' }}
      </button>
    </form>

    <p class="text-center text-xs text-slate dark:text-slate-dark mt-6">
      {{ mode === 'login' ? "Don't have an account?" : 'Already have an account?' }}
      <button
        @click="mode = mode === 'login' ? 'register' : 'login'; error = ''"
        class="text-teal dark:text-teal-dark font-medium hover:underline cursor-pointer"
      >
        {{ mode === 'login' ? 'Sign up' : 'Sign in' }}
      </button>
    </p>
  </div>
</template>
