<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import type { DocumentRecord } from '@/api/types'

const documents = ref<DocumentRecord[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const filterBrochures = ref(false)
const filterInsurer = ref('')

onMounted(async () => {
  try {
    documents.value = await api.getDocuments()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load documents'
  } finally {
    loading.value = false
  }
})

const insurers = computed(() =>
  [...new Set(documents.value.map(d => d.insurer))].sort()
)

const filtered = computed(() => {
  let list = documents.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(d =>
      d.title.toLowerCase().includes(q) ||
      d.insurer.toLowerCase().includes(q) ||
      d.product_type.toLowerCase().includes(q)
    )
  }
  if (filterBrochures.value) {
    list = list.filter(d => d.is_brochure)
  }
  if (filterInsurer.value) {
    list = list.filter(d => d.insurer === filterInsurer.value)
  }
  return list
})

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="section-title">Documents & Brochures</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">
          {{ documents.length }} documents · {{ documents.filter(d => d.is_brochure).length }} brochures
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search documents..."
          class="input-field w-48"
        />
        <select v-model="filterInsurer" class="select-field w-36">
          <option value="">All insurers</option>
          <option v-for="ins in insurers" :key="ins" :value="ins">{{ ins }}</option>
        </select>
        <label class="flex items-center gap-2 text-xs text-slate dark:text-slate-dark cursor-pointer">
          <input v-model="filterBrochures" type="checkbox" class="rounded border-black/20 dark:border-white/20 text-teal dark:text-teal-dark focus:ring-teal/30" />
          Brochures only
        </label>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card p-8">
      <div class="animate-pulse space-y-3">
        <div v-for="i in 6" :key="i" class="h-14 bg-black/5 dark:bg-white/5 rounded"></div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-6 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark">{{ error }}</p>
    </div>

    <!-- Document List -->
    <div v-else-if="filtered.length > 0" class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-black/5 dark:border-white/10 text-left">
              <th class="px-5 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Document</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Insurer</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Type</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Pages</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide">Downloaded</th>
              <th class="px-4 py-2.5 font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide text-center">Kind</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="doc in filtered"
              :key="doc.id"
              class="border-b border-black/[0.03] dark:border-white/[0.04] hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
            >
              <td class="px-5 py-3">
                <div class="flex items-center gap-2">
                  <svg class="w-4 h-4 text-slate/50 dark:text-slate-dark/50 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span class="font-medium text-xs truncate max-w-[240px]">{{ doc.title }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-xs">{{ doc.insurer }}</td>
              <td class="px-4 py-3">
                <span class="badge-silent">{{ doc.product_type }}</span>
              </td>
              <td class="px-4 py-3 text-center font-mono text-xs">{{ doc.page_count ?? '—' }}</td>
              <td class="px-4 py-3 text-xs text-slate dark:text-slate-dark">{{ formatDate(doc.downloaded_at) }}</td>
              <td class="px-4 py-3 text-center">
                <span :class="doc.is_brochure ? 'badge-limited' : 'badge-covered'">
                  {{ doc.is_brochure ? 'Brochure' : 'Policy' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="card p-12 text-center">
      <svg class="w-12 h-12 mx-auto text-slate/30 dark:text-slate-dark/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="mt-3 text-sm font-medium text-slate dark:text-slate-dark">No documents found</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">Run the crawler pipeline to download policy documents and brochures.</p>
    </div>
  </div>
</template>
