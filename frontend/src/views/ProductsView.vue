<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { ProductSummary } from '@/api/types'
import { formatLabel } from '@/utils/format'

/**
 * Cross-category product catalog - every real, distinct named product
 * across every insurer, browsable as products first (not insurers first).
 * Complements Compare (which grades/diffs products within one category at
 * a time) by giving a flat, searchable "what exists" view across all of
 * them at once.
 */

const router = useRouter()
const products = ref<ProductSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')

onMounted(async () => {
  try {
    products.value = await api.getProducts()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load products'
  } finally {
    loading.value = false
  }
})

// Light grouping for readability - purely a display grouping, not a new
// taxonomy/data-model concept (see ReportView/CompareView for where the
// real product_type categories live).
const RISK_AREAS: { label: string; types: string[] }[] = [
  { label: 'Life & Health', types: ['life_cover', 'tpd', 'trauma', 'income_protection', 'health'] },
  { label: 'Home & Property', types: ['house', 'contents', 'home_contents', 'landlord'] },
  { label: 'Vehicle', types: ['car'] },
  { label: 'Travel & Leisure', types: ['travel', 'boat'] },
  { label: 'Pet', types: ['pet'] },
  { label: 'Business', types: ['business'] },
]

function riskAreaFor(productType: string): string {
  return RISK_AREAS.find((a) => a.types.includes(productType))?.label ?? 'Other'
}

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return products.value
  return products.value.filter(
    (p) =>
      p.product_name.toLowerCase().includes(q) ||
      p.insurer.toLowerCase().includes(q) ||
      p.product_type.toLowerCase().includes(q)
  )
})

const grouped = computed(() => {
  const groups = new Map<string, ProductSummary[]>()
  for (const p of filtered.value) {
    const area = riskAreaFor(p.product_type)
    if (!groups.has(area)) groups.set(area, [])
    groups.get(area)!.push(p)
  }
  // Stable, sensible order matching RISK_AREAS, with "Other" last.
  const order = [...RISK_AREAS.map((a) => a.label), 'Other']
  return order
    .filter((label) => groups.has(label))
    .map((label) => ({
      label,
      items: groups.get(label)!.sort((a, b) => a.product_name.localeCompare(b.product_name)),
    }))
})

function productDisplayName(name: string): string {
  return name === name.toLowerCase() ? formatLabel(name) : name
}

function goCompare(p: ProductSummary) {
  router.push({ path: '/compare', query: { type: p.product_type } })
}
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="section-title">Product Catalog</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">
          {{ products.length }} distinct products across every insurer we track
        </p>
      </div>
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search products or insurers..."
        class="input-field w-64"
      />
    </div>

    <div v-if="loading" class="card p-8">
      <div class="animate-pulse space-y-4">
        <div v-for="i in 5" :key="i" class="h-12 bg-black/5 dark:bg-white/5 rounded"></div>
      </div>
    </div>

    <div v-else-if="error" class="card p-6 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark">{{ error }}</p>
    </div>

    <template v-else>
      <section v-for="group in grouped" :key="group.label" class="space-y-3">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate dark:text-slate-dark">
          {{ group.label }} <span class="font-mono normal-case text-[10px]">({{ group.items.length }})</span>
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <button
            v-for="p in group.items"
            :key="p.policy_version_id"
            type="button"
            class="card p-4 text-left hover:border-teal/40 dark:hover:border-teal-dark/40 transition-colors cursor-pointer"
            @click="goCompare(p)"
          >
            <h4 class="text-sm font-semibold truncate">{{ productDisplayName(p.product_name) }}</h4>
            <p class="text-xs text-slate dark:text-slate-dark truncate mt-0.5">{{ p.insurer }}</p>
            <div class="flex items-center justify-between mt-3">
              <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-black/5 dark:bg-white/10 text-slate dark:text-slate-dark">
                {{ formatLabel(p.product_type) }}
              </span>
              <span class="text-[10px] font-mono text-slate dark:text-slate-dark">{{ p.fact_count }} facts</span>
            </div>
          </button>
        </div>
      </section>

      <div v-if="filtered.length === 0" class="card p-12 text-center">
        <p class="text-sm text-slate dark:text-slate-dark">No products match your search.</p>
      </div>
    </template>
  </div>
</template>
