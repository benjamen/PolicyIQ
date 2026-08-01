<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import type { InsurerCoverage, PipelineRun } from '@/api/types'

const insurers = ref<InsurerCoverage[]>([])
const pipelineRuns = ref<PipelineRun[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const stats = ref({
  totalInsurers: 0,
  coveredSlots: 0,
  totalSlots: 0,
  lastRunStatus: '—' as string,
  documentsProcessed: 0,
})

onMounted(async () => {
  try {
    const [cov, runs] = await Promise.allSettled([
      api.getInsurerCoverage(),
      api.getPipelineRuns(10),
    ])

    if (cov.status === 'fulfilled') {
      insurers.value = cov.value
      const allTypes = cov.value.flatMap(i => i.types)
      stats.value.totalInsurers = cov.value.length
      stats.value.coveredSlots = allTypes.filter(t => t.covered).length
      stats.value.totalSlots = allTypes.length
    }

    if (runs.status === 'fulfilled') {
      pipelineRuns.value = runs.value
      if (runs.value.length > 0) {
        stats.value.lastRunStatus = runs.value[0].status
        stats.value.documentsProcessed = runs.value.reduce((s, r) => s + r.documents_found, 0)
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard data'
  } finally {
    loading.value = false
  }
})

const coveragePercent = () =>
  stats.value.totalSlots > 0
    ? Math.round((stats.value.coveredSlots / stats.value.totalSlots) * 100)
    : 0
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- KPI Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Insurers</p>
        <p class="stat-value mt-1 text-teal dark:text-teal-dark">{{ stats.totalInsurers }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">tracked in registry</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Coverage</p>
        <p class="stat-value mt-1">{{ coveragePercent() }}%</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">{{ stats.coveredSlots }}/{{ stats.totalSlots }} product slots</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Documents</p>
        <p class="stat-value mt-1">{{ stats.documentsProcessed }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">processed in pipeline</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Last Run</p>
        <p class="stat-value mt-1 capitalize" :class="{
          'text-teal dark:text-teal-dark': stats.lastRunStatus === 'completed',
          'text-amber dark:text-amber-dark': stats.lastRunStatus === 'partial',
          'text-brick dark:text-brick-dark': stats.lastRunStatus === 'failed',
        }">{{ stats.lastRunStatus }}</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">pipeline status</p>
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
      <p class="text-sm text-brick dark:text-brick-dark font-medium">Failed to load data</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">{{ error }}</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-2">Ensure the backend API is running on port 8000.</p>
    </div>

    <!-- Coverage Grid -->
    <div v-else-if="insurers.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10">
        <h2 class="section-title">Insurer Coverage Matrix</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">Product types with verified document extractions</p>
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
                    {{ t.product_type }}
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
      <p class="text-xs text-slate dark:text-slate-dark mt-1">Run the ingestion pipeline to populate the database.</p>
    </div>

    <!-- Recent Pipeline Runs -->
    <div v-if="pipelineRuns.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10">
        <h2 class="section-title">Recent Pipeline Runs</h2>
      </div>
      <div class="divide-y divide-black/[0.03] dark:divide-white/[0.04]">
        <div v-for="run in pipelineRuns.slice(0, 5)" :key="run.id" class="flex items-center justify-between px-5 py-3">
          <div class="flex items-center gap-3">
            <span class="w-2 h-2 rounded-full" :class="{
              'bg-teal dark:bg-teal-dark': run.status === 'completed',
              'bg-amber dark:bg-amber-dark': run.status === 'partial' || run.status === 'running',
              'bg-brick dark:bg-brick-dark': run.status === 'failed',
            }"></span>
            <span class="text-sm font-medium">{{ run.insurer }}</span>
          </div>
          <div class="flex items-center gap-4 text-xs text-slate dark:text-slate-dark font-mono">
            <span>{{ run.documents_found }} docs</span>
            <span>{{ run.extractions_ok }} ok</span>
            <span v-if="run.extractions_failed > 0" class="text-brick dark:text-brick-dark">{{ run.extractions_failed }} failed</span>
            <span>{{ new Date(run.started_at).toLocaleDateString('en-NZ') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
