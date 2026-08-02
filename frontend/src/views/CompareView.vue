<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import type {
  CompareLifeResponse,
  CompareGeneralResponse,
  GradeReport,
  GeneralProductProfile,
  GeneralInsuranceFact,
  FactCategory,
  SourceRef,
  CriterionOut,
} from '@/api/types'
import Citation from '@/components/Citation.vue'
import SourceDrawer from '@/components/SourceDrawer.vue'
import ScoreDial from '@/components/ScoreDial.vue'
import CriterionRow from '@/components/CriterionRow.vue'
import { formatLabel } from '@/utils/format'

// Each insurance type is its own top-level "split". `kind` selects which
// comparison engine renders it: a fact-based policy diff (general) or graded
// scorecards (life). Health uses the general fact-diff too - it shows real
// data once health policies are ingested, and a "check back soon" empty
// state until then.
type CategoryKind = 'general' | 'life'
interface CategoryDef {
  value: string
  label: string
  kind: CategoryKind
}

const categories: CategoryDef[] = [
  { value: 'house', label: 'Home', kind: 'general' },
  { value: 'contents', label: 'Contents', kind: 'general' },
  { value: 'car', label: 'Car', kind: 'general' },
  { value: 'landlord', label: 'Landlord', kind: 'general' },
  { value: 'boat', label: 'Boat', kind: 'general' },
  { value: 'travel', label: 'Travel', kind: 'general' },
  { value: 'pet', label: 'Pet', kind: 'general' },
  { value: 'life', label: 'Life', kind: 'life' },
  { value: 'health', label: 'Health', kind: 'general' },
]

const activeCategory = ref('house')
const activeKind = computed(
  () => categories.find((c) => c.value === activeCategory.value)?.kind ?? 'general'
)

const loading = ref(false)
const error = ref<string | null>(null)
const dataSource = ref<string | null>(null)

// ---- General insurance state ----
const generalResults = ref<GeneralProductProfile[]>([])
const searchQuery = ref('')
const activeCategories = ref<Set<FactCategory>>(new Set(['benefit', 'limit', 'exclusion']))
const excludedInsurers = ref<Set<string>>(new Set())

const CATEGORY_META: Record<FactCategory, { label: string; dot: string; text: string; chip: string }> = {
  benefit: {
    label: 'Benefits',
    dot: 'bg-teal dark:bg-teal-dark',
    text: 'text-teal dark:text-teal-dark',
    chip: 'bg-teal-soft dark:bg-teal-soft-dark text-teal dark:text-teal-dark',
  },
  limit: {
    label: 'Limits & sub-limits',
    dot: 'bg-amber dark:bg-amber-dark',
    text: 'text-amber dark:text-amber-dark',
    chip: 'bg-amber-soft dark:bg-amber-soft/20 text-amber dark:text-amber-dark',
  },
  exclusion: {
    label: 'Exclusions',
    dot: 'bg-brick dark:bg-brick-dark',
    text: 'text-brick dark:text-brick-dark',
    chip: 'bg-brick-soft dark:bg-brick-soft/20 text-brick dark:text-brick-dark',
  },
}
const CATEGORY_ORDER: FactCategory[] = ['benefit', 'limit', 'exclusion']

// ---- Life insurance state ----
const lifeFilters = ref({
  age: 35,
  smoker_status: 'non_smoker' as 'non_smoker' | 'smoker',
  occupation_category: 'professional',
  product_type: 'life_cover',
})
const lifeResults = ref<GradeReport[]>([])
const expandedExclusions = ref<Set<string>>(new Set())

const occupationCategories = ['professional', 'clerical', 'manual', 'hazardous']
const lifeProductTypes = ['life_cover', 'tpd', 'trauma', 'income_protection']

// ---- Life scoring methodology (mirrors backend DEFAULT_WEIGHTS) ----
const CRITERIA_META: Record<string, { label: string; blurb: string }> = {
  tpd_definition: {
    label: 'TPD definition',
    blurb: 'How strictly total & permanent disability is defined - own-occupation pays out most easily.',
  },
  trauma_conditions: {
    label: 'Trauma conditions',
    blurb: 'Breadth of the critical-illness condition list you can claim on.',
  },
  occupation_restrictions: {
    label: 'Occupation restrictions',
    blurb: 'Whether cover is available, loaded, or excluded for your occupation.',
  },
  premium_structure: {
    label: 'Premium structure',
    blurb: 'Level vs stepped premiums, and whether they are guaranteed.',
  },
  waiver_of_premium: {
    label: 'Waiver of premium',
    blurb: 'Your cover continues without payments while you are on claim.',
  },
  automatic_benefits: {
    label: 'Automatic benefits',
    blurb: 'Built-in extras included at no additional cost.',
  },
}
const CRITERIA_WEIGHTS: Record<string, number> = {
  tpd_definition: 0.25,
  trauma_conditions: 0.2,
  occupation_restrictions: 0.2,
  premium_structure: 0.15,
  waiver_of_premium: 0.1,
  automatic_benefits: 0.1,
}
const methodology = computed(() => {
  const max = Math.max(...Object.values(CRITERIA_WEIGHTS))
  return Object.entries(CRITERIA_META)
    .map(([key, m]) => ({
      key,
      ...m,
      weight: CRITERIA_WEIGHTS[key] ?? 0,
      bar: Math.round(((CRITERIA_WEIGHTS[key] ?? 0) / max) * 100),
    }))
    .sort((a, b) => b.weight - a.weight)
})

function criteriaEntries(report: GradeReport): [string, CriterionOut][] {
  return Object.entries(report.criteria).sort((a, b) => b[1].weight - a[1].weight)
}

// ---- Citation drawer ----
const drawerSource = ref<SourceRef | null>(null)
function openSource(source: SourceRef) {
  drawerSource.value = source
}

// ---- Data fetching ----
async function runGeneralCompare() {
  loading.value = true
  error.value = null
  dataSource.value = null
  excludedInsurers.value = new Set()
  try {
    const res: CompareGeneralResponse = await api.compareGeneral({ product_type: activeCategory.value })
    generalResults.value = res.results
    dataSource.value = res.data_source
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Comparison failed'
    generalResults.value = []
  } finally {
    loading.value = false
  }
}

async function runLifeCompare() {
  loading.value = true
  error.value = null
  dataSource.value = null
  try {
    const res: CompareLifeResponse = await api.compareLife(lifeFilters.value)
    lifeResults.value = res.results
    dataSource.value = res.data_source
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Grading failed'
    lifeResults.value = []
  } finally {
    loading.value = false
  }
}

// Auto-run the general comparison whenever a general category is selected.
watch(activeCategory, (cat) => {
  if (categories.find((c) => c.value === cat)?.kind === 'general') runGeneralCompare()
})

// Run the default (Home) comparison on mount.
runGeneralCompare()

// ---- General derived data ----
const sortedGeneralResults = computed(() =>
  [...generalResults.value].sort((a, b) => b.facts.length - a.facts.length)
)

const visibleGeneralResults = computed(() =>
  sortedGeneralResults.value.filter((p) => !excludedInsurers.value.has(p.policy_version_id))
)

function profileStats(p: GeneralProductProfile) {
  return {
    benefit: p.facts.filter((f) => f.category === 'benefit').length,
    limit: p.facts.filter((f) => f.category === 'limit').length,
    exclusion: p.facts.filter((f) => f.category === 'exclusion').length,
  }
}

function matchesSearch(f: GeneralInsuranceFact): boolean {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  return (
    f.name.toLowerCase().includes(q) ||
    (f.detail ?? '').toLowerCase().includes(q)
  )
}

function visibleFacts(p: GeneralProductProfile, cat: FactCategory): GeneralInsuranceFact[] {
  return p.facts.filter((f) => f.category === cat && matchesSearch(f))
}

const generalTotals = computed(() => {
  const facts = generalResults.value.flatMap((p) => p.facts)
  return {
    insurers: generalResults.value.length,
    facts: facts.length,
    benefit: facts.filter((f) => f.category === 'benefit').length,
    limit: facts.filter((f) => f.category === 'limit').length,
    exclusion: facts.filter((f) => f.category === 'exclusion').length,
  }
})

function toggleInsurer(id: string) {
  const next = new Set(excludedInsurers.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  excludedInsurers.value = next
}

function toggleCategory(cat: FactCategory) {
  const next = new Set(activeCategories.value)
  if (next.has(cat)) next.delete(cat)
  else next.add(cat)
  activeCategories.value = next
}

// ---- Life derived data ----
const sortedLifeResults = computed(() =>
  [...lifeResults.value].sort((a, b) => (b.overall_score ?? -1) - (a.overall_score ?? -1))
)

function toggleExclusions(id: string) {
  const next = new Set(expandedExclusions.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedExclusions.value = next
}

function completenessTone(c: number): string {
  if (c >= 0.8) return 'bg-teal dark:bg-teal-dark'
  if (c >= 0.5) return 'bg-amber dark:bg-amber-dark'
  return 'bg-brick dark:bg-brick-dark'
}
</script>

<template>
  <div class="space-y-6 max-w-7xl">
    <!-- ===== Header ===== -->
    <div>
      <h1 class="text-xl font-semibold tracking-tight">Compare Policies</h1>
      <p class="text-sm text-slate dark:text-slate-dark mt-0.5">
        Document-grounded comparison — every figure is cited to the insurer's published policy.
      </p>
    </div>

    <!-- ===== Insurance type splits ===== -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="c in categories"
        :key="c.value"
        @click="activeCategory = c.value"
        class="px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all duration-150 cursor-pointer"
        :class="activeCategory === c.value
          ? 'bg-teal dark:bg-teal-dark text-white border-teal dark:border-teal-dark shadow-sm'
          : 'border-black/10 dark:border-white/15 text-slate dark:text-slate-dark hover:border-teal/40 dark:hover:border-teal-dark/40 hover:text-ink dark:hover:text-ink-dark'"
      >
        {{ c.label }}
      </button>
    </div>

    <!-- ===== Error ===== -->
    <div v-if="error" class="card p-4 border-brick/30">
      <p class="text-sm text-brick dark:text-brick-dark">{{ error }}</p>
    </div>

    <!-- ============================================================ -->
    <!-- ===== GENERAL INSURANCE — POLICY DETAIL DIFF ===== -->
    <!-- ============================================================ -->
    <template v-if="activeKind === 'general'">
      <!-- Summary stats + data source -->
      <div v-if="generalResults.length > 0" class="card px-5 py-4 flex flex-wrap items-center gap-x-8 gap-y-3">
        <div>
          <p class="stat-value text-xl">{{ generalTotals.insurers }}</p>
          <p class="text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark">insurers</p>
        </div>
        <div>
          <p class="stat-value text-xl">{{ generalTotals.facts }}</p>
          <p class="text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark">extracted facts</p>
        </div>
        <div class="flex items-center gap-4">
          <span v-for="cat in CATEGORY_ORDER" :key="cat" class="flex items-center gap-1.5 text-xs">
            <span class="w-2 h-2 rounded-full" :class="CATEGORY_META[cat].dot"></span>
            <span class="font-mono tabular-nums">{{ generalTotals[cat] }}</span>
            <span class="text-slate dark:text-slate-dark">{{ CATEGORY_META[cat].label.toLowerCase() }}</span>
          </span>
        </div>
        <div class="ml-auto flex items-center gap-2 text-xs text-slate dark:text-slate-dark">
          <span class="w-1.5 h-1.5 rounded-full bg-teal dark:bg-teal-dark"></span>
          <span class="font-mono">{{ dataSource }}</span>
        </div>
      </div>

      <!-- Search + category filters -->
      <div v-if="generalResults.length > 0" class="flex flex-wrap items-center gap-3">
        <div class="relative flex-1 min-w-[220px] max-w-sm">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate dark:text-slate-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            v-model="searchQuery"
            type="search"
            placeholder="Search benefits, limits, exclusions…"
            class="input-field pl-9"
          />
        </div>
        <div class="flex items-center gap-1.5">
          <button
            v-for="cat in CATEGORY_ORDER"
            :key="cat"
            @click="toggleCategory(cat)"
            class="px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-150 cursor-pointer"
            :class="activeCategories.has(cat)
              ? CATEGORY_META[cat].chip
              : 'bg-black/5 dark:bg-white/5 text-slate dark:text-slate-dark opacity-60'"
          >
            {{ CATEGORY_META[cat].label }}
          </button>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <div v-for="i in 6" :key="i" class="card p-5 animate-pulse">
          <div class="h-4 rounded bg-black/5 dark:bg-white/10 w-2/5 mb-3"></div>
          <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-full mb-2"></div>
          <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-4/5 mb-2"></div>
          <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-3/5"></div>
        </div>
      </div>

      <!-- Insurer columns -->
      <div v-else-if="visibleGeneralResults.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-start">
        <div
          v-for="profile in visibleGeneralResults"
          :key="profile.policy_version_id"
          class="card overflow-hidden"
        >
          <!-- Card header -->
          <div class="px-4 py-3.5 border-b border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <h3 class="font-semibold text-sm truncate" :title="profile.insurer">{{ profile.insurer }}</h3>
                <p class="text-[11px] text-slate dark:text-slate-dark truncate mt-0.5">{{ profile.product_name }}</p>
              </div>
              <button
                type="button"
                class="shrink-0 p-1 rounded text-slate dark:text-slate-dark hover:text-brick dark:hover:text-brick-dark hover:bg-brick-soft dark:hover:bg-brick-soft/20 transition-colors cursor-pointer"
                title="Hide this insurer"
                @click="toggleInsurer(profile.policy_version_id)"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              </button>
            </div>
            <div class="flex items-center gap-1.5 mt-2.5">
              <span
                v-for="cat in CATEGORY_ORDER"
                :key="cat"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="CATEGORY_META[cat].chip"
              >
                {{ profileStats(profile)[cat] }} {{ CATEGORY_META[cat].label.toLowerCase() }}
              </span>
            </div>
          </div>

          <!-- Fact groups -->
          <div class="px-4 py-3 space-y-4">
            <template v-for="cat in CATEGORY_ORDER" :key="cat">
              <div v-if="activeCategories.has(cat) && visibleFacts(profile, cat).length > 0">
                <div class="flex items-center gap-2 mb-2">
                  <span class="w-1.5 h-1.5 rounded-full" :class="CATEGORY_META[cat].dot"></span>
                  <p class="text-[10px] font-semibold uppercase tracking-wider" :class="CATEGORY_META[cat].text">
                    {{ CATEGORY_META[cat].label }}
                  </p>
                  <span class="text-[10px] font-mono text-slate dark:text-slate-dark">{{ visibleFacts(profile, cat).length }}</span>
                </div>
                <ul class="space-y-2.5">
                  <li v-for="fact in visibleFacts(profile, cat)" :key="`${profile.policy_version_id}-${cat}-${fact.name}`" class="pl-3.5 border-l-2 border-black/5 dark:border-white/10">
                    <p class="text-xs font-medium leading-snug">{{ fact.name }}</p>
                    <p v-if="fact.detail" class="font-mono text-xs tabular-nums mt-0.5" :class="CATEGORY_META[cat].text">
                      {{ fact.detail }}
                    </p>
                    <Citation
                      v-if="fact.source"
                      :source="fact.source"
                      class="mt-1.5"
                      @open="openSource"
                    />
                  </li>
                </ul>
              </div>
            </template>

            <p
              v-if="CATEGORY_ORDER.every((c) => !activeCategories.has(c) || visibleFacts(profile, c).length === 0)"
              class="text-xs text-slate dark:text-slate-dark italic py-2"
            >
              No facts match the current filters.
            </p>
          </div>
        </div>
      </div>

      <!-- Hidden insurers restore bar -->
      <div v-if="excludedInsurers.size > 0 && !loading" class="flex flex-wrap items-center gap-2 text-xs text-slate dark:text-slate-dark">
        <span>Hidden:</span>
        <button
          v-for="profile in sortedGeneralResults.filter((p) => excludedInsurers.has(p.policy_version_id))"
          :key="profile.policy_version_id"
          @click="toggleInsurer(profile.policy_version_id)"
          class="px-2.5 py-1 rounded-full border border-black/10 dark:border-white/15 hover:border-teal/40 dark:hover:border-teal-dark/40 hover:text-ink dark:hover:text-ink-dark transition-colors cursor-pointer"
        >
          {{ profile.insurer }} ↩
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="!loading && generalResults.length === 0 && dataSource !== null" class="card p-12 text-center">
        <p class="text-sm font-medium text-slate dark:text-slate-dark">No verified comparisons for this category yet</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">We're adding more insurers and products — check back soon.</p>
      </div>
    </template>

    <!-- ============================================================ -->
    <!-- ===== LIFE INSURANCE — GRADED SCORECARDS ===== -->
    <!-- ============================================================ -->
    <template v-else>
      <!-- Filters -->
      <div class="card p-5">
        <div class="flex flex-wrap items-end gap-4">
          <div>
            <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Age</label>
            <input v-model.number="lifeFilters.age" type="number" min="18" max="75" class="input-field w-24" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Smoker status</label>
            <select v-model="lifeFilters.smoker_status" class="select-field w-36">
              <option value="non_smoker">Non-smoker</option>
              <option value="smoker">Smoker</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Occupation</label>
            <select v-model="lifeFilters.occupation_category" class="select-field w-36">
              <option v-for="oc in occupationCategories" :key="oc" :value="oc">{{ formatLabel(oc) }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate dark:text-slate-dark mb-1.5">Product</label>
            <select v-model="lifeFilters.product_type" class="select-field w-44">
              <option v-for="pt in lifeProductTypes" :key="pt" :value="pt">{{ formatLabel(pt) }}</option>
            </select>
          </div>
          <button @click="runLifeCompare" :disabled="loading" class="btn-primary">
            <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Grade policies
          </button>
        </div>
        <p class="text-[10px] text-slate dark:text-slate-dark mt-3">
          Informational comparison of policy structure and eligibility only — not a premium quote or financial advice.
        </p>
      </div>

      <!-- Methodology -->
      <div class="card p-5">
        <div class="flex items-start gap-2.5">
          <svg class="w-4 h-4 text-teal dark:text-teal-dark shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div class="min-w-0">
            <h3 class="text-sm font-semibold">How the score works</h3>
            <p class="text-xs text-slate dark:text-slate-dark mt-1 leading-relaxed max-w-3xl">
              Each policy is graded by a fixed, deterministic rulebook &mdash; not an AI opinion. Six weighted
              criteria are scored 0&ndash;100 from extracted, cited policy facts. If a fact hasn&rsquo;t been extracted
              yet it&rsquo;s excluded from the average (never scored as zero), so an incompletely processed policy
              isn&rsquo;t unfairly penalised. Click any citation to read the source clause.
            </p>
          </div>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-3 mt-4">
          <div v-for="m in methodology" :key="m.key">
            <div class="flex items-baseline justify-between gap-1">
              <span class="text-[11px] font-medium truncate">{{ m.label }}</span>
              <span class="text-[10px] font-mono text-slate dark:text-slate-dark shrink-0">{{ Math.round(m.weight * 100) }}%</span>
            </div>
            <div class="h-1 rounded-full bg-black/5 dark:bg-white/10 mt-1.5 overflow-hidden">
              <div class="h-full rounded-full bg-teal dark:bg-teal-dark" :style="{ width: m.bar + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-4">
        <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
          <div class="flex gap-5">
            <div class="w-[72px] h-[72px] rounded-full bg-black/5 dark:bg-white/10"></div>
            <div class="flex-1 space-y-2">
              <div class="h-4 rounded bg-black/5 dark:bg-white/10 w-1/3"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-1/2"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Scorecards -->
      <div v-else-if="sortedLifeResults.length > 0" class="space-y-4">
        <div
          v-for="(report, idx) in sortedLifeResults"
          :key="report.policy_version_id"
          class="card overflow-hidden"
          :class="!report.eligible ? 'opacity-70' : ''"
        >
          <!-- Top match banner -->
          <div
            v-if="idx === 0 && report.eligible"
            class="flex items-center gap-1.5 px-5 py-1.5 bg-teal dark:bg-teal-dark text-white text-[11px] font-medium"
          >
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2l2.9 6.26L21.5 9l-5 4.87L17.8 21 12 17.27 6.2 21l1.3-7.13-5-4.87 6.6-.74L12 2z" />
            </svg>
            Top match for your profile
          </div>

          <div class="p-5">
            <!-- Header: rank + dial + identity -->
            <div class="flex items-center gap-5">
              <div class="flex flex-col items-center gap-1 shrink-0">
                <span class="text-[10px] font-mono text-slate dark:text-slate-dark">#{{ idx + 1 }}</span>
                <ScoreDial :score="report.overall_score" :size="76" />
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="font-semibold text-base">{{ report.insurer }}</h3>
                  <span class="text-xs text-slate dark:text-slate-dark">{{ report.product_name }}</span>
                  <span v-if="!report.eligible" class="badge-excluded">Ineligible</span>
                </div>
                <p v-if="!report.eligible" class="text-xs text-brick dark:text-brick-dark mt-1">{{ report.ineligibility_reason }}</p>

                <div class="flex items-center gap-x-5 gap-y-2 mt-2.5 flex-wrap text-xs">
                  <div class="flex items-center gap-1.5">
                    <span class="text-slate dark:text-slate-dark">Overall</span>
                    <span class="font-mono font-semibold tabular-nums">{{ report.overall_score === null ? '—' : report.overall_score.toFixed(1) }}</span>
                    <span class="text-slate dark:text-slate-dark">/100</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-slate dark:text-slate-dark">Data completeness</span>
                    <div class="w-20 h-1 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
                      <div class="h-full rounded-full" :class="completenessTone(report.data_completeness)" :style="{ width: (report.data_completeness * 100) + '%' }"></div>
                    </div>
                    <span class="font-mono tabular-nums">{{ Math.round(report.data_completeness * 100) }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Line-by-line score breakdown -->
            <div v-if="Object.keys(report.criteria).length > 0" class="mt-4 border-t border-black/5 dark:border-white/10">
              <p class="text-[10px] uppercase tracking-wider font-semibold text-slate dark:text-slate-dark pt-3.5 pb-1">
                Score breakdown &middot; line by line
              </p>
              <div class="divide-y divide-black/5 dark:divide-white/10">
                <CriterionRow
                  v-for="[name, criterion] in criteriaEntries(report)"
                  :key="String(name)"
                  :criterion="criterion"
                  :label="CRITERIA_META[String(name)]?.label ?? String(name).replace(/_/g, ' ')"
                  :blurb="CRITERIA_META[String(name)]?.blurb ?? ''"
                  @open="openSource"
                />
              </div>
            </div>

            <!-- Exclusions accordion -->
            <div v-if="report.exclusions.length > 0" class="mt-2 border-t border-black/5 dark:border-white/10 pt-3">
              <button
                type="button"
                class="flex items-center gap-2 text-xs font-medium text-slate dark:text-slate-dark hover:text-ink dark:hover:text-ink-dark transition-colors cursor-pointer"
                @click="toggleExclusions(report.policy_version_id)"
              >
                <svg class="w-3.5 h-3.5 transition-transform duration-200" :class="expandedExclusions.has(report.policy_version_id) ? 'rotate-90' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                {{ report.exclusions.length }} exclusion{{ report.exclusions.length === 1 ? '' : 's' }} noted
              </button>
              <ul v-if="expandedExclusions.has(report.policy_version_id)" class="mt-3 space-y-2 pl-5">
                <li v-for="exc in report.exclusions" :key="`${report.policy_version_id}-exc-${exc.name}`" class="flex items-start justify-between gap-3">
                  <span class="text-xs text-ink/80 dark:text-ink-dark/80">{{ exc.name }}</span>
                  <Citation v-if="exc.source" :source="exc.source" compact @open="openSource" />
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-if="!loading && lifeResults.length === 0 && dataSource !== null" class="card p-12 text-center">
        <p class="text-sm font-medium text-slate dark:text-slate-dark">No graded policies for these filters</p>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">We're still analysing policies for this product type — check back soon.</p>
      </div>
    </template>

    <!-- ===== Citation source drawer ===== -->
    <SourceDrawer :source="drawerSource" @close="drawerSource = null" />
  </div>
</template>
