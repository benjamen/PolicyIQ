<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type { CompareLifeResponse, CompareGeneralResponse, GradeReport, GeneralProductProfile } from '@/api/types'

type Mode = 'life' | 'general'

const mode = ref<Mode>('general')
const loading = ref(false)
const error = ref<string | null>(null)

// Life insurance filters
const lifeFilters = ref({
  age: 35,
  smoker_status: 'non_smoker' as 'non_smoker' | 'smoker',
  occupation_category: 'professional',
  product_type: 'life_cover',
})

// General insurance filters
const generalProductType = ref('house')

const lifeResults = ref<GradeReport[]>([])
const generalResults = ref<GeneralProductProfile[]>([])
const dataSource = ref<string | null>(null)

const occupationCategories = ['professional', 'clerical', 'manual', 'hazardous']
const lifeProductTypes = ['life_cover', 'tpd', 'trauma', 'income_protection']
const generalProductTypes = ['house', 'contents', 'travel', 'motor']

async function runCompare() {
  loading.value = true
  error.value = null
  lifeResults.value = []
  generalResults.value = []

  try {
    if (mode.value === 'life') {
      const res: CompareLifeResponse = await api.compareLife(lifeFilters.value)
      lifeResults.value = res.results
      dataSource.value = res.data_source
    } else {
      const res: CompareGeneralResponse = await api.compareGeneral({ product_type: generalProductType.value })
      generalResults.value = res.results
      dataSource.value = res.data_source
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Comparison failed'
  } finally {
    loading.value = false
  }
}

const sortedLifeResults = computed(() =>
  [...lifeResults.value].sort((a, b) => (b.overall_score ?? 0) - (a.overall_score ?? 0))
)

function scoreColor(score: number | null): string {
  if (score === null) return 'text-slate dark:text-slate-dark'
  if (score >= 0.7) return 'text-teal dark:text-teal-dark'
  if (score >= 0.4) return 'text-amber dark:text-amber-dark'
  return 'text-brick dark:text-brick-dark'
}

function scoreBar(score: number | null): string {
  if (score === null) return '0%'
  return `${Math.round(score * 100)}%`
}
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Mode Toggle -->
    <div class="flex items-center gap-1 p-1 rounded-lg bg-black/5 dark:bg-white/5 w-fit">
      <button
        v-for="m in (['general', 'life'] as Mode[])"
        :key="m"
        @click="mode = m"
        class="px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-150 cursor-pointer"
        :class="mode === m
          ? 'bg-paper-raised dark:bg-paper-raised-dark shadow-sm text-ink dark:text-ink-dark'
          : 'text-slate dark:text-slate-dark hover:text-ink dark:hover:text-ink-dark'"
      >
        {{ m === 'general' ? 'General Insurance' : 'Life Insurance' }}
      </button>
    </div>

    <!-- Filters -->
    <div class="card p-5">
      <div v-if="mode === 'general'" class="flex flex-wrap items-end gap-4">
        <div>
          <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Product Type</label>
          <select v-model="generalProductType" class="select-field w-44">
            <option v-for="pt in generalProductTypes" :key="pt" :value="pt">{{ pt }}</option>
          </select>
        </div>
        <button @click="runCompare" :disabled="loading" class="btn-primary">
          <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Compare
        </button>
      </div>

      <div v-else class="flex flex-wrap items-end gap-4">
        <div>
          <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Age</label>
          <input v-model.number="lifeFilters.age" type="number" min="18" max="75" class="input-field w-24" />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Smoker</label>
          <select v-model="lifeFilters.smoker_status" class="select-field w-36">
            <option value="non_smoker">Non-smoker</option>
            <option value="smoker">Smoker</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Occupation</label>
          <select v-model="lifeFilters.occupation_category" class="select-field w-36">
            <option v-for="oc in occupationCategories" :key="oc" :value="oc">{{ oc }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Product</label>
          <select v-model="lifeFilters.product_type" class="select-field w-40">
            <option v-for="pt in lifeProductTypes" :key="pt" :value="pt">{{ pt.replace('_', ' ') }}</option>
          </select>
        </div>
        <button @click="runCompare" :disabled="loading" class="btn-primary">
          <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Grade
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="card p-4 border-brick/20">
      <p class="text-sm text-brick dark:text-brick-dark">{{ error }}</p>
    </div>

    <!-- Data source indicator -->
    <div v-if="dataSource" class="flex items-center gap-2 text-xs text-slate dark:text-slate-dark">
      <span class="w-1.5 h-1.5 rounded-full bg-teal dark:bg-teal-dark"></span>
      Data source: <span class="font-mono">{{ dataSource }}</span>
    </div>

    <!-- Life Insurance Results (Graded) -->
    <div v-if="mode === 'life' && sortedLifeResults.length > 0" class="space-y-4">
      <div v-for="(report, idx) in sortedLifeResults" :key="report.policy_version_id" class="card p-5">
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-slate dark:text-slate-dark">#{{ idx + 1 }}</span>
              <h3 class="font-semibold text-sm">{{ report.insurer }}</h3>
              <span class="text-xs text-slate dark:text-slate-dark">{{ report.product_name }}</span>
            </div>
            <div v-if="!report.eligible" class="mt-1">
              <span class="badge-excluded">Ineligible</span>
              <span class="text-xs text-slate dark:text-slate-dark ml-2">{{ report.ineligibility_reason }}</span>
            </div>
          </div>
          <div class="text-right">
            <p class="stat-value text-lg" :class="scoreColor(report.overall_score)">
              {{ report.overall_score !== null ? (report.overall_score * 100).toFixed(0) : '—' }}
            </p>
            <p class="text-[10px] text-slate dark:text-slate-dark uppercase">score</p>
          </div>
        </div>

        <!-- Score bar -->
        <div class="mt-3 h-1.5 rounded-full bg-black/5 dark:bg-white/5 overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="report.overall_score !== null
              ? (report.overall_score >= 0.7 ? 'bg-teal dark:bg-teal-dark' : report.overall_score >= 0.4 ? 'bg-amber dark:bg-amber-dark' : 'bg-brick dark:bg-brick-dark')
              : ''"
            :style="{ width: scoreBar(report.overall_score) }"
          ></div>
        </div>

        <!-- Criteria breakdown -->
        <div v-if="Object.keys(report.criteria).length > 0" class="mt-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <div v-for="(criterion, name) in report.criteria" :key="name" class="text-center">
            <p class="text-xs font-mono" :class="scoreColor(criterion.score)">{{ (criterion.score * 100).toFixed(0) }}</p>
            <p class="text-[10px] text-slate dark:text-slate-dark capitalize mt-0.5">{{ String(name).replace(/_/g, ' ') }}</p>
          </div>
        </div>

        <!-- Data completeness -->
        <div class="mt-3 flex items-center gap-2 text-[10px] text-slate dark:text-slate-dark">
          <span>Data completeness: {{ (report.data_completeness * 100).toFixed(0) }}%</span>
          <span v-if="report.exclusions.length > 0">· {{ report.exclusions.length }} exclusions noted</span>
        </div>
      </div>
    </div>

    <!-- General Insurance Results (Diff view) -->
    <div v-if="mode === 'general' && generalResults.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10">
        <h2 class="section-title">{{ generalProductType }} Insurance — Fact Comparison</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">{{ generalResults.length }} insurers with verified extractions</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-black/5 dark:border-white/10">
              <th class="px-5 py-2.5 text-left font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide sticky left-0 bg-paper-raised dark:bg-paper-raised-dark">Category / Fact</th>
              <th
                v-for="profile in generalResults"
                :key="profile.policy_version_id"
                class="px-4 py-2.5 text-left font-medium text-xs text-slate dark:text-slate-dark uppercase tracking-wide min-w-[200px]"
              >
                {{ profile.insurer }}
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="profile in generalResults" :key="profile.policy_version_id">
              <tr
                v-for="fact in profile.facts"
                :key="`${profile.policy_version_id}-${fact.name}`"
                class="border-b border-black/[0.03] dark:border-white/[0.04] hover:bg-black/[0.02] dark:hover:bg-white/[0.02]"
              >
                <td class="px-5 py-2 sticky left-0 bg-paper-raised dark:bg-paper-raised-dark">
                  <span class="text-xs font-medium">{{ fact.name }}</span>
                  <span class="block text-[10px] text-slate dark:text-slate-dark">{{ fact.category }}</span>
                </td>
                <td class="px-4 py-2">
                  <p class="text-xs leading-relaxed">{{ fact.detail }}</p>
                  <p v-if="fact.source?.verified" class="text-[10px] text-teal dark:text-teal-dark mt-0.5 font-mono">
                    ✓ p.{{ fact.source.page ?? '?' }}
                  </p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty results -->
    <div v-if="!loading && !error && lifeResults.length === 0 && generalResults.length === 0 && dataSource !== null" class="card p-12 text-center">
      <p class="text-sm font-medium text-slate dark:text-slate-dark">No results for these filters</p>
      <p class="text-xs text-slate dark:text-slate-dark mt-1">The database may not yet contain verified extractions for this product type.</p>
    </div>
  </div>
</template>
