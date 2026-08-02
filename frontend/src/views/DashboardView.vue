<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import type { InsurerCoverage } from '@/api/types'
import { formatLabel } from '@/utils/format'

const insurers = ref<InsurerCoverage[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const stats = ref({
  totalInsurers: 0,
  coveredSlots: 0,
  documentCount: 0,
})

onMounted(async () => {
  try {
    const [cov, docs] = await Promise.allSettled([
      api.getInsurerCoverage(),
      api.getDocuments(),
    ])

    if (cov.status === 'fulfilled') {
      insurers.value = cov.value
      const allTypes = cov.value.flatMap(i => i.types)
      stats.value.totalInsurers = cov.value.length
      stats.value.coveredSlots = allTypes.filter(t => t.covered).length
    }

    if (docs.status === 'fulfilled') {
      stats.value.documentCount = docs.value.length
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard data'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Hero -->
    <section class="hero-panel px-6 py-8 sm:px-8 sm:py-10">
      <!-- Decorative shield watermark -->
      <svg class="pointer-events-none absolute -right-6 -bottom-8 w-56 h-56 text-white/[0.06]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="0.75">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
      <div class="relative max-w-2xl">
        <p class="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">Evidence-grounded insurance intelligence</p>
        <h1 class="mt-3 text-2xl sm:text-3xl font-semibold tracking-tight leading-tight">
          Compare NZ insurance on the facts, not the marketing.
        </h1>
        <p class="mt-3 text-sm text-white/80 leading-relaxed">
          Every score and claim on PolicyIQ is extracted from real policy documents and brochures -
          and ships with a citation you can verify yourself.
        </p>
        <div class="mt-6 flex flex-wrap items-center gap-3">
          <router-link to="/compare" class="hero-cta-primary">
            Compare insurers
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
          </router-link>
          <router-link to="/documents" class="hero-cta-secondary">Browse source documents</router-link>
        </div>
      </div>
    </section>

    <!-- KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="card p-4">
        <div class="flex items-center justify-between">
          <p class="eyebrow">Insurers</p>
          <span class="icon-chip !w-8 !h-8">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
          </span>
        </div>
        <p class="stat-value mt-2 text-teal dark:text-teal-dark">{{ stats.totalInsurers }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">NZ insurers compared</p>
      </div>
      <div class="card p-4">
        <div class="flex items-center justify-between">
          <p class="eyebrow">Source documents</p>
          <span class="icon-chip !w-8 !h-8">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          </span>
        </div>
        <p class="stat-value mt-2">{{ stats.documentCount }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">policies & brochures analysed</p>
      </div>
      <div class="card p-4">
        <div class="flex items-center justify-between">
          <p class="eyebrow">Product types</p>
          <span class="icon-chip !w-8 !h-8">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
          </span>
        </div>
        <p class="stat-value mt-2">{{ stats.coveredSlots }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">with verified cover data</p>
      </div>
    </div>

    <!-- Loading / Error states -->
    <div v-if="loading" class="card p-8 text-center">
      <div class="animate-pulse space-y-3">
        <div class="h-4 bg-black/5 dark:bg-white/5 rounded w-1/3 mx-auto"></div>
        <div class="h-3 bg-black/5 dark:bg-white/5 rounded w-1/2 mx-auto"></div>
      </div>
    </div>

    <div v-else-if="error" class="card p-6 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark font-medium">We couldn't load the latest data</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">Please try again in a moment.</p>
    </div>

    <!-- Coverage Grid -->
    <div v-else-if="insurers.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10">
        <h2 class="section-title">Insurer Coverage Matrix</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">Product types we compare per insurer</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-black/5 dark:border-white/10 text-left">
              <th class="px-5 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Insurer</th>
              <th class="px-3 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Products</th>
              <th class="px-3 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Covered</th>
              <th class="px-5 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Types</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="insurer in insurers"
              :key="insurer.name"
              class="border-b border-black/[0.03] dark:border-white/[0.04] hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
            >
              <td class="px-5 py-2.5 font-medium">{{ insurer.name }}</td>
              <td class="px-3 py-2.5 text-center font-mono text-xs">{{ insurer.types.length }}</td>
              <td class="px-3 py-2.5 text-center font-mono text-xs text-teal dark:text-teal-dark">
                {{ insurer.types.filter(t => t.covered).length }}
              </td>
              <td class="px-5 py-2.5">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="t in insurer.types"
                    :key="t.product_type"
                    class="badge"
                    :class="t.covered ? 'badge-covered' : 'badge-silent'"
                  >
                    {{ formatLabel(t.product_type) }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="card p-12 text-center">
      <svg class="w-12 h-12 mx-auto text-slate/30 dark:text-slate-dark/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p class="mt-3 text-sm font-medium text-slate dark:text-slate-dark">No insurer data yet</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">Check back soon - we're adding more insurers and products.</p>
    </div>
  </div>
</template>
