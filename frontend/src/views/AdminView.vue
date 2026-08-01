<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import type { PipelineRun } from '@/api/types'

const runs = ref<PipelineRun[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    runs.value = await api.getPipelineRuns(50)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load pipeline runs'
  } finally {
    loading.value = false
  }
})

const summary = computed(() => {
  const total = runs.value.length
  const completed = runs.value.filter(r => r.status === 'completed').length
  const failed = runs.value.filter(r => r.status === 'failed').length
  const partial = runs.value.filter(r => r.status === 'partial').length
  const totalDocs = runs.value.reduce((s, r) => s + r.documents_found, 0)
  const totalNew = runs.value.reduce((s, r) => s + r.documents_new, 0)
  const totalOk = runs.value.reduce((s, r) => s + r.extractions_ok, 0)
  const totalFailed = runs.value.reduce((s, r) => s + r.extractions_failed, 0)
  return { total, completed, failed, partial, totalDocs, totalNew, totalOk, totalFailed }
})

function statusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-teal dark:text-teal-dark'
    case 'partial': return 'text-amber dark:text-amber-dark'
    case 'failed': return 'text-brick dark:text-brick-dark'
    default: return 'text-slate dark:text-slate-dark'
  }
}

function statusDot(status: string): string {
  switch (status) {
    case 'completed': return 'bg-teal dark:bg-teal-dark'
    case 'partial': return 'bg-amber dark:bg-amber-dark'
    case 'failed': return 'bg-brick dark:bg-brick-dark'
    default: return 'bg-slate dark:bg-slate-dark'
  }
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-NZ', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  })
}

function duration(run: PipelineRun): string {
  if (!run.finished_at) return 'running...'
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Summary Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Total Runs</p>
        <p class="stat-value mt-1">{{ summary.total }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Success Rate</p>
        <p class="stat-value mt-1 text-teal dark:text-teal-dark">
          {{ summary.total > 0 ? Math.round((summary.completed / summary.total) * 100) : 0 }}%
        </p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Documents</p>
        <p class="stat-value mt-1">{{ summary.totalDocs }}</p>
        <p class="text-xs text-teal dark:text-teal-dark">{{ summary.totalNew }} new</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-slate dark:text-slate-dark uppercase tracking-wide">Extractions</p>
        <p class="stat-value mt-1">{{ summary.totalOk }}</p>
        <p v-if="summary.totalFailed > 0" class="text-xs text-brick dark:text-brick-dark">{{ summary.totalFailed }} failed</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card p-8">
      <div class="animate-pulse space-y-3">
        <div v-for="i in 8" :key="i" class="h-10 bg-black/5 dark:bg-white/5 rounded"></div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-6 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark font-medium">Pipeline data unavailable</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">{{ error }}</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-2">
        The pipeline_run table requires the scraping architecture migration (a1b2c3d4e5f6).
      </p>
    </div>

    <!-- Run History -->
    <div v-else-if="runs.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10">
        <h2 class="section-title">Run History</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">Weekly full scan · Mon 02:00 NZST · 6 staggered insurer groups</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-black/5 dark:border-white/10 text-left">
              <th class="px-5 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Status</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Insurer</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Docs</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">New</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">OK</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Failed</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Duration</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Started</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in runs"
              :key="run.id"
              class="border-b border-black/[0.03] dark:border-white/[0.04] hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
            >
              <td class="px-5 py-2.5">
                <div class="flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full" :class="statusDot(run.status)"></span>
                  <span class="text-xs font-medium capitalize" :class="statusColor(run.status)">{{ run.status }}</span>
                </div>
              </td>
              <td class="px-4 py-2.5 text-xs font-medium">{{ run.insurer }}</td>
              <td class="px-4 py-2.5 text-center font-mono text-xs">{{ run.documents_found }}</td>
              <td class="px-4 py-2.5 text-center font-mono text-xs text-teal dark:text-teal-dark">{{ run.documents_new }}</td>
              <td class="px-4 py-2.5 text-center font-mono text-xs">{{ run.extractions_ok }}</td>
              <td class="px-4 py-2.5 text-center font-mono text-xs" :class="run.extractions_failed > 0 ? 'text-brick dark:text-brick-dark' : ''">{{ run.extractions_failed }}</td>
              <td class="px-4 py-2.5 text-xs font-mono text-slate dark:text-slate-dark">{{ duration(run) }}</td>
              <td class="px-4 py-2.5 text-xs text-slate dark:text-slate-dark">{{ formatDateTime(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="card p-12 text-center">
      <svg class="w-12 h-12 mx-auto text-slate/30 dark:text-slate-dark/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <p class="mt-3 text-sm font-medium text-slate dark:text-slate-dark">No pipeline runs recorded</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">
        Run <code class="font-mono bg-black/5 dark:bg-white/5 px-1 rounded">python -m app.pipeline.orchestrator --mode once</code> to trigger a scan.
      </p>
    </div>

    <!-- Schedule Info -->
    <div class="card p-5">
      <h3 class="text-sm font-semibold mb-3">Weekly Schedule</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 02:00</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group A — IAG/Suncorp (AMI, State, NZI)</p>
        </div>
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 02:30</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group B — Tower, Vero, AA Insurance</p>
        </div>
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 03:00</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group C — Mutuals (FMG, MAS, Trade Me)</p>
        </div>
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 03:30</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group D — Life (AIA, Partners, Fidelity)</p>
        </div>
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 04:00</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group E — Health (Southern Cross, nib)</p>
        </div>
        <div class="p-3 rounded-md bg-black/[0.02] dark:bg-white/[0.03]">
          <p class="font-medium text-teal dark:text-teal-dark">Mon 04:30</p>
          <p class="text-slate dark:text-slate-dark mt-0.5">Group F — Specialty (SPCA, Cove, 1Cover)</p>
        </div>
      </div>
    </div>
  </div>
</template>
