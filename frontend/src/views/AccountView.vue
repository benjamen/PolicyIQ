<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { user, isAuthenticated, getToken, logout } = useAuth()

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface ApiKeyItem {
  id: string
  label: string
  key_prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

const keys = ref<ApiKeyItem[]>([])
const newKeyLabel = ref('')
const createdKey = ref('')  // shown once
const loading = ref(false)
const error = ref('')

function authHeaders(): Record<string, string> {
  return { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' }
}

async function loadKeys() {
  try {
    const res = await fetch(`${BASE}/api-keys`, { headers: authHeaders() })
    if (res.ok) keys.value = await res.json()
  } catch { /* ignore */ }
}

async function createKey() {
  error.value = ''
  createdKey.value = ''
  loading.value = true
  try {
    const res = await fetch(`${BASE}/api-keys`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ label: newKeyLabel.value || 'default' }),
    })
    const data = await res.json()
    if (res.ok) {
      createdKey.value = data.raw_key
      newKeyLabel.value = ''
      await loadKeys()
    } else {
      error.value = data.detail || 'Failed to create key'
    }
  } catch {
    error.value = 'Network error'
  } finally {
    loading.value = false
  }
}

async function revokeKey(id: string) {
  try {
    await fetch(`${BASE}/api-keys/${id}`, { method: 'DELETE', headers: authHeaders() })
    await loadKeys()
  } catch { /* ignore */ }
}

function doLogout() {
  logout()
  router.push('/')
}

function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' })
}

onMounted(() => {
  if (!isAuthenticated.value) {
    router.push('/login')
    return
  }
  loadKeys()
})
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-8">
    <!-- Profile card -->
    <section class="rounded-xl border border-black/5 dark:border-white/10 bg-paper-raised dark:bg-paper-raised-dark p-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold">{{ user?.name || user?.email || 'Account' }}</h2>
          <p class="text-sm text-slate dark:text-slate-dark">{{ user?.email }}</p>
        </div>
        <button @click="doLogout" class="text-xs px-3 py-1.5 rounded-lg border border-black/10 dark:border-white/15 hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer">
          Sign out
        </button>
      </div>

      <div class="grid grid-cols-3 gap-4 mt-6">
        <div class="rounded-lg bg-teal-soft/60 dark:bg-teal-soft-dark/60 p-3 text-center">
          <p class="text-lg font-bold text-teal dark:text-teal-dark">{{ user?.credit_balance ?? 0 }}</p>
          <p class="text-[11px] text-slate dark:text-slate-dark">Credits</p>
        </div>
        <div class="rounded-lg bg-black/5 dark:bg-white/5 p-3 text-center">
          <p class="text-lg font-bold">{{ user?.subscription_active ? 'Active' : 'None' }}</p>
          <p class="text-[11px] text-slate dark:text-slate-dark">Subscription</p>
        </div>
        <div class="rounded-lg bg-black/5 dark:bg-white/5 p-3 text-center">
          <p class="text-lg font-bold capitalize">{{ user?.role ?? '—' }}</p>
          <p class="text-[11px] text-slate dark:text-slate-dark">Role</p>
        </div>
      </div>
    </section>

    <!-- API Keys -->
    <section class="rounded-xl border border-black/5 dark:border-white/10 bg-paper-raised dark:bg-paper-raised-dark p-6">
      <h3 class="text-sm font-semibold mb-4">API Keys</h3>
      <p class="text-xs text-slate dark:text-slate-dark mb-4">
        Use API keys to access the PolicyIQ comparison API programmatically.
        Each head-to-head comparison costs 1 credit.
      </p>

      <!-- Created key alert -->
      <div v-if="createdKey" class="mb-4 p-3 rounded-lg bg-teal-soft dark:bg-teal-soft-dark border border-teal/20 dark:border-teal-dark/20">
        <p class="text-xs font-medium text-teal dark:text-teal-dark mb-1">Copy your new key now — it won't be shown again:</p>
        <code class="text-xs font-mono break-all bg-white/60 dark:bg-white/10 px-2 py-1 rounded">{{ createdKey }}</code>
      </div>

      <!-- Create form -->
      <div class="flex gap-2 mb-4">
        <input
          v-model="newKeyLabel"
          type="text"
          placeholder="Key label (e.g. production)"
          class="flex-1 px-3 py-2 rounded-lg border border-black/10 dark:border-white/15 bg-white dark:bg-white/5 text-sm focus:outline-none focus:ring-2 focus:ring-teal/40"
        />
        <button
          @click="createKey"
          :disabled="loading"
          class="px-4 py-2 rounded-lg bg-teal dark:bg-teal-dark text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
        >
          {{ loading ? '…' : 'Create' }}
        </button>
      </div>

      <p v-if="error" class="text-xs text-brick mb-3">{{ error }}</p>

      <!-- Key list -->
      <div class="space-y-2">
        <div
          v-for="key in keys"
          :key="key.id"
          class="flex items-center justify-between px-3 py-2.5 rounded-lg border border-black/5 dark:border-white/10"
          :class="key.revoked_at ? 'opacity-50' : ''"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium truncate">{{ key.label }}</p>
            <p class="text-[11px] text-slate dark:text-slate-dark font-mono">{{ key.key_prefix }}… · created {{ formatDate(key.created_at) }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span v-if="key.revoked_at" class="text-[11px] text-brick">Revoked</span>
            <span v-else-if="key.last_used_at" class="text-[11px] text-slate dark:text-slate-dark">Used {{ formatDate(key.last_used_at) }}</span>
            <button
              v-if="!key.revoked_at"
              @click="revokeKey(key.id)"
              class="text-[11px] px-2 py-1 rounded border border-brick/30 text-brick hover:bg-brick/10 transition-colors cursor-pointer"
            >
              Revoke
            </button>
          </div>
        </div>
        <p v-if="keys.length === 0" class="text-xs text-slate dark:text-slate-dark py-2">No API keys yet.</p>
      </div>
    </section>

    <!-- Pricing info -->
    <section class="rounded-xl border border-black/5 dark:border-white/10 bg-paper-raised dark:bg-paper-raised-dark p-6">
      <h3 class="text-sm font-semibold mb-3">Plans</h3>
      <div class="grid grid-cols-2 gap-4">
        <div class="rounded-lg border border-teal/30 dark:border-teal-dark/30 p-4">
          <p class="text-sm font-semibold text-teal dark:text-teal-dark">Subscription — $49/mo</p>
          <p class="text-xs text-slate dark:text-slate-dark mt-1">Unlimited head-to-head comparisons via UI + API. Named-user access.</p>
        </div>
        <div class="rounded-lg border border-black/10 dark:border-white/15 p-4">
          <p class="text-sm font-semibold">Company API — $20/credit</p>
          <p class="text-xs text-slate dark:text-slate-dark mt-1">1 credit = 1 comparison. Minimum 10 credits/month. Pooled across users.</p>
        </div>
      </div>
    </section>
  </div>
</template>
