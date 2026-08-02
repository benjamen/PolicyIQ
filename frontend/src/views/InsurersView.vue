<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import type { InsurerCoverage } from '@/api/types'
import { formatLabel } from '@/utils/format'

const insurers = ref<InsurerCoverage[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const filterCovered = ref(false)

onMounted(async () => {
  try {
    insurers.value = await api.getInsurerCoverage()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load insurers'
  } finally {
    loading.value = false
  }
})

const filtered = computed(() => {
  let list = insurers.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q))
  }
  if (filterCovered.value) {
    list = list.filter(i => i.types.some(t => t.covered))
  }
  return list
})

const totalCovered = computed(() =>
  insurers.value.reduce((s, i) => s + i.types.filter(t => t.covered).length, 0)
)
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="section-title">Insurer Directory</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">
          {{ insurers.length }} insurers · {{ totalCovered }} verified product slots
        </p>
      </div>
      <div class="flex items-center gap-3">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search insurers..."
          class="input-field w-48"
        />
        <label class="flex items-center gap-2 text-xs text-slate dark:text-slate-dark cursor-pointer">
          <input v-model="filterCovered" type="checkbox" class="rounded border-black/20 dark:border-white/20 text-teal dark:text-teal-dark focus:ring-teal/30" />
          Has data
        </label>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card p-8">
      <div class="animate-pulse space-y-4">
        <div v-for="i in 5" :key="i" class="h-12 bg-black/5 dark:bg-white/5 rounded"></div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-6 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark">{{ error }}</p>
    </div>

    <!-- Insurer Cards -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-for="insurer in filtered" :key="insurer.name" class="card p-5">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-lg bg-teal-soft dark:bg-teal-soft-dark flex items-center justify-center">
              <span class="text-sm font-bold text-teal dark:text-teal-dark">{{ insurer.name.charAt(0) }}</span>
            </div>
            <div>
              <h3 class="text-sm font-semibold">{{ insurer.name }}</h3>
              <p class="text-xs text-slate dark:text-slate-dark">{{ insurer.types.length }} product types</p>
            </div>
          </div>
          <span
            class="badge"
            :class="insurer.types.some(t => t.covered) ? 'badge-covered' : 'badge-silent'"
          >
            {{ insurer.types.some(t => t.covered) ? 'Active' : 'Pending' }}
          </span>
        </div>

        <!-- Product type chips -->
        <div class="flex flex-wrap gap-1.5 mt-4">
          <span
            v-for="t in insurer.types"
            :key="t.product_type"
            class="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border transition-colors"
            :class="t.covered
              ? 'border-teal/20 dark:border-teal-dark/20 bg-teal-soft dark:bg-teal-soft-dark text-teal dark:text-teal-dark'
              : 'border-black/5 dark:border-white/10 text-slate dark:text-slate-dark'"
          >
            <span class="w-1.5 h-1.5 rounded-full" :class="t.covered ? 'bg-teal dark:bg-teal-dark' : 'bg-slate/30 dark:bg-slate-dark/30'"></span>
            {{ formatLabel(t.product_type) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!loading && !error && filtered.length === 0" class="card p-12 text-center">
      <p class="text-sm text-slate dark:text-slate-dark">No insurers match your filters.</p>
    </div>
  </div>
</template>
