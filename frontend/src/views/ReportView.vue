<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import type {
  GradeReport,
  GeneralProductProfile,
  SourceRef,
  CriterionOut,
  FactCategory,
} from '@/api/types'
import Citation from '@/components/Citation.vue'
import SourceDrawer from '@/components/SourceDrawer.vue'
import ScoreDial from '@/components/ScoreDial.vue'
import { formatLabel } from '@/utils/format'

/**
 * Head-to-head report: exactly two insurers, one product type, a single
 * shareable URL. Reuses the same /compare/life and /compare/general
 * endpoints CompareView.vue already calls (no new backend surface) and
 * narrows the results down to the two selected policy_version_ids -
 * "winner" for life is just whichever of the two has the higher
 * already-server-computed score, no new scoring logic needed here.
 *
 * General insurance report has no winner column, same reasoning as
 * CompareView's general mode: it's a document diff, not a graded score.
 */

const route = useRoute()

const kind = computed(() => (route.query.kind === 'life' ? 'life' : 'general'))
const productType = computed(() => String(route.query.type ?? 'house'))
const idA = computed(() => String(route.query.a ?? ''))
const idB = computed(() => String(route.query.b ?? ''))
const age = computed(() => Number(route.query.age ?? 35))
const smoker = computed(() => (route.query.smoker === 'smoker' ? 'smoker' : 'non_smoker') as 'smoker' | 'non_smoker')
const occupation = computed(() => String(route.query.occupation ?? 'professional'))

const loading = ref(true)
const error = ref<string | null>(null)

const lifeA = ref<GradeReport | null>(null)
const lifeB = ref<GradeReport | null>(null)
const generalA = ref<GeneralProductProfile | null>(null)
const generalB = ref<GeneralProductProfile | null>(null)

const CRITERIA_META: Record<string, string> = {
  tpd_definition: 'TPD definition',
  trauma_conditions: 'Trauma conditions',
  occupation_restrictions: 'Occupation restrictions',
  premium_structure: 'Premium structure',
  waiver_of_premium: 'Waiver of premium',
  automatic_benefits: 'Automatic benefits',
}
const CRITERIA_WEIGHTS: Record<string, number> = {
  tpd_definition: 0.25,
  trauma_conditions: 0.2,
  occupation_restrictions: 0.2,
  premium_structure: 0.15,
  waiver_of_premium: 0.1,
  automatic_benefits: 0.1,
}

async function load() {
  loading.value = true
  error.value = null
  try {
    if (kind.value === 'life') {
      const res = await api.compareLife({
        age: age.value,
        smoker_status: smoker.value,
        occupation_category: occupation.value,
        product_type: productType.value,
      })
      lifeA.value = res.results.find((r) => r.policy_version_id === idA.value) ?? null
      lifeB.value = res.results.find((r) => r.policy_version_id === idB.value) ?? null
      if (!lifeA.value || !lifeB.value) error.value = 'One or both insurers in this report are no longer available for these filters.'
    } else {
      const res = await api.compareGeneral({ product_type: productType.value })
      generalA.value = res.results.find((p) => p.policy_version_id === idA.value) ?? null
      generalB.value = res.results.find((p) => p.policy_version_id === idB.value) ?? null
      if (!generalA.value || !generalB.value) error.value = 'One or both insurers in this report are no longer available for this product type.'
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load report'
  } finally {
    loading.value = false
  }
}
onMounted(load)

const criteriaRows = computed(() => {
  if (!lifeA.value || !lifeB.value) return []
  const keys = new Set([...Object.keys(lifeA.value.criteria), ...Object.keys(lifeB.value.criteria)])
  return [...keys]
    .sort((x, y) => (CRITERIA_WEIGHTS[y] ?? 0) - (CRITERIA_WEIGHTS[x] ?? 0))
    .map((key) => ({
      key,
      label: CRITERIA_META[key] ?? formatLabel(key),
      a: lifeA.value!.criteria[key] as CriterionOut | undefined,
      b: lifeB.value!.criteria[key] as CriterionOut | undefined,
    }))
})

function winner(a?: CriterionOut, b?: CriterionOut): 'a' | 'b' | 'tie' | null {
  if (!a || a.score === null || !b || b.score === null) return null
  if (a.score === b.score) return 'tie'
  return a.score > b.score ? 'a' : 'b'
}

const overallWinner = computed(() => {
  if (!lifeA.value || !lifeB.value) return null
  const a = lifeA.value.overall_score
  const b = lifeB.value.overall_score
  if (a === null || b === null) return null
  if (a === b) return 'tie'
  return a > b ? 'a' : 'b'
})

const CATEGORY_ORDER: FactCategory[] = ['benefit', 'limit', 'exclusion']
const CATEGORY_LABEL: Record<FactCategory, string> = { benefit: 'Benefits', limit: 'Limits & sub-limits', exclusion: 'Exclusions' }

function factsFor(profile: GeneralProductProfile | null, cat: FactCategory) {
  return profile ? profile.facts.filter((f) => f.category === cat) : []
}

const drawerSource = ref<SourceRef | null>(null)
function openSource(source: SourceRef) {
  drawerSource.value = source
}

const shareCopied = ref(false)
function copyShareLink() {
  navigator.clipboard.writeText(window.location.href).then(() => {
    shareCopied.value = true
    setTimeout(() => (shareCopied.value = false), 2000)
  })
}

const generatedAt = new Date().toLocaleDateString('en-NZ', { day: 'numeric', month: 'long', year: 'numeric' })

function printReport() {
  window.print()
}
</script>

<template>
  <div class="max-w-5xl mx-auto space-y-6 print:space-y-4">
    <!-- Loading -->
    <div v-if="loading" class="card p-12 text-center">
      <p class="text-sm text-slate dark:text-slate-dark">Generating report…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-sm font-medium text-brick dark:text-brick-dark">{{ error }}</p>
      <router-link to="/compare" class="btn-primary inline-flex mt-4">Back to Compare</router-link>
    </div>

    <template v-else>
      <!-- ===== Report header ===== -->
      <div class="card p-6 print:border-0 print:shadow-none print:p-0">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark font-medium">Head-to-head report</p>
            <h1 class="text-xl font-semibold tracking-tight mt-1">
              {{ kind === 'life' ? lifeA?.insurer : generalA?.insurer }}
              <span class="text-slate dark:text-slate-dark font-normal mx-1.5">vs</span>
              {{ kind === 'life' ? lifeB?.insurer : generalB?.insurer }}
            </h1>
            <p class="text-xs text-slate dark:text-slate-dark mt-1">
              {{ formatLabel(productType) }} · generated {{ generatedAt }}
              <span v-if="kind === 'life'"> · age {{ age }}, {{ smoker === 'smoker' ? 'smoker' : 'non-smoker' }}, {{ formatLabel(occupation) }}</span>
            </p>
          </div>
          <div class="flex items-center gap-2 print:hidden">
            <button @click="copyShareLink" class="btn-secondary text-xs">
              {{ shareCopied ? 'Link copied' : 'Copy share link' }}
            </button>
            <button @click="printReport" class="btn-primary text-xs">Print / Save as PDF</button>
          </div>
        </div>
      </div>

      <!-- ===== LIFE: overall score comparison ===== -->
      <div v-if="kind === 'life' && lifeA && lifeB" class="card p-6 flex items-center justify-center gap-10 print:border-0 print:shadow-none">
        <div class="flex flex-col items-center gap-2">
          <ScoreDial :score="lifeA.overall_score" :size="88" />
          <p class="text-sm font-semibold">{{ lifeA.insurer }}</p>
          <span v-if="overallWinner === 'a'" class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-teal-soft dark:bg-teal-soft-dark text-teal dark:text-teal-dark">Higher overall score</span>
          <span v-if="!lifeA.eligible" class="badge-excluded">Ineligible: {{ lifeA.ineligibility_reason }}</span>
        </div>
        <div class="text-xs text-slate dark:text-slate-dark font-mono">vs</div>
        <div class="flex flex-col items-center gap-2">
          <ScoreDial :score="lifeB.overall_score" :size="88" />
          <p class="text-sm font-semibold">{{ lifeB.insurer }}</p>
          <span v-if="overallWinner === 'b'" class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-teal-soft dark:bg-teal-soft-dark text-teal dark:text-teal-dark">Higher overall score</span>
          <span v-if="!lifeB.eligible" class="badge-excluded">Ineligible: {{ lifeB.ineligibility_reason }}</span>
        </div>
      </div>

      <!-- ===== LIFE: criterion-by-criterion table ===== -->
      <div v-if="kind === 'life' && lifeA && lifeB" class="card overflow-hidden print:border-0 print:shadow-none">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
              <th class="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark font-semibold">Criterion</th>
              <th class="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark font-semibold">{{ lifeA.insurer }}</th>
              <th class="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark font-semibold">{{ lifeB.insurer }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-black/5 dark:divide-white/10">
            <tr v-for="row in criteriaRows" :key="row.key">
              <td class="px-4 py-3 align-top">
                <p class="text-xs font-medium">{{ row.label }}</p>
                <p class="text-[10px] text-slate dark:text-slate-dark mt-0.5">{{ Math.round((CRITERIA_WEIGHTS[row.key] ?? 0) * 100) }}% weight</p>
              </td>
              <td class="px-4 py-3 align-top" :class="winner(row.a, row.b) === 'a' ? 'bg-teal-soft/40 dark:bg-teal-soft-dark/20' : ''">
                <div v-if="row.a">
                  <div class="flex items-center gap-1.5">
                    <span class="font-mono text-xs tabular-nums font-semibold">{{ row.a.score === null ? '—' : Math.round(row.a.score) }}</span>
                    <span v-if="winner(row.a, row.b) === 'a'" class="text-[9px] font-medium text-teal dark:text-teal-dark">WINNER</span>
                  </div>
                  <p class="text-[11px] text-slate dark:text-slate-dark mt-0.5">{{ row.a.raw_value }}</p>
                  <Citation v-if="row.a.source" :source="row.a.source" compact class="mt-1.5" @open="openSource" />
                </div>
                <span v-else class="text-xs text-slate dark:text-slate-dark italic">not extracted</span>
              </td>
              <td class="px-4 py-3 align-top" :class="winner(row.a, row.b) === 'b' ? 'bg-teal-soft/40 dark:bg-teal-soft-dark/20' : ''">
                <div v-if="row.b">
                  <div class="flex items-center gap-1.5">
                    <span class="font-mono text-xs tabular-nums font-semibold">{{ row.b.score === null ? '—' : Math.round(row.b.score) }}</span>
                    <span v-if="winner(row.a, row.b) === 'b'" class="text-[9px] font-medium text-teal dark:text-teal-dark">WINNER</span>
                  </div>
                  <p class="text-[11px] text-slate dark:text-slate-dark mt-0.5">{{ row.b.raw_value }}</p>
                  <Citation v-if="row.b.source" :source="row.b.source" compact class="mt-1.5" @open="openSource" />
                </div>
                <span v-else class="text-xs text-slate dark:text-slate-dark italic">not extracted</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ===== LIFE: exclusions side by side ===== -->
      <div v-if="kind === 'life' && lifeA && lifeB" class="grid grid-cols-2 gap-4 print:break-inside-avoid">
        <div class="card p-4">
          <p class="text-[10px] uppercase tracking-wider font-semibold text-slate dark:text-slate-dark mb-2">{{ lifeA.insurer }} — exclusions</p>
          <ul class="space-y-2">
            <li v-for="exc in lifeA.exclusions" :key="exc.name" class="text-xs">
              {{ exc.name }}
              <Citation v-if="exc.source" :source="exc.source" compact class="mt-1" @open="openSource" />
            </li>
            <li v-if="lifeA.exclusions.length === 0" class="text-xs text-slate dark:text-slate-dark italic">None noted</li>
          </ul>
        </div>
        <div class="card p-4">
          <p class="text-[10px] uppercase tracking-wider font-semibold text-slate dark:text-slate-dark mb-2">{{ lifeB.insurer }} — exclusions</p>
          <ul class="space-y-2">
            <li v-for="exc in lifeB.exclusions" :key="exc.name" class="text-xs">
              {{ exc.name }}
              <Citation v-if="exc.source" :source="exc.source" compact class="mt-1" @open="openSource" />
            </li>
            <li v-if="lifeB.exclusions.length === 0" class="text-xs text-slate dark:text-slate-dark italic">None noted</li>
          </ul>
        </div>
      </div>

      <!-- ===== GENERAL: side-by-side fact diff (no winner - document diff, not a score) ===== -->
      <template v-if="kind === 'general' && generalA && generalB">
        <div v-for="cat in CATEGORY_ORDER" :key="cat" class="card overflow-hidden print:break-inside-avoid">
          <div class="px-4 py-2.5 border-b border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
            <p class="text-[10px] uppercase tracking-wider font-semibold text-slate dark:text-slate-dark">{{ CATEGORY_LABEL[cat] }}</p>
          </div>
          <div class="grid grid-cols-2 divide-x divide-black/5 dark:divide-white/10">
            <div class="p-4">
              <p class="text-xs font-semibold mb-2">{{ generalA.insurer }} <span class="text-slate dark:text-slate-dark font-normal">({{ factsFor(generalA, cat).length }})</span></p>
              <ul class="space-y-2.5">
                <li v-for="f in factsFor(generalA, cat)" :key="f.name" class="text-xs">
                  <p class="font-medium">{{ f.name }}</p>
                  <p v-if="f.detail" class="font-mono text-[11px] text-slate dark:text-slate-dark mt-0.5">{{ f.detail }}</p>
                  <Citation v-if="f.source" :source="f.source" compact class="mt-1" @open="openSource" />
                </li>
                <li v-if="factsFor(generalA, cat).length === 0" class="text-xs text-slate dark:text-slate-dark italic">None noted</li>
              </ul>
            </div>
            <div class="p-4">
              <p class="text-xs font-semibold mb-2">{{ generalB.insurer }} <span class="text-slate dark:text-slate-dark font-normal">({{ factsFor(generalB, cat).length }})</span></p>
              <ul class="space-y-2.5">
                <li v-for="f in factsFor(generalB, cat)" :key="f.name" class="text-xs">
                  <p class="font-medium">{{ f.name }}</p>
                  <p v-if="f.detail" class="font-mono text-[11px] text-slate dark:text-slate-dark mt-0.5">{{ f.detail }}</p>
                  <Citation v-if="f.source" :source="f.source" compact class="mt-1" @open="openSource" />
                </li>
                <li v-if="factsFor(generalB, cat).length === 0" class="text-xs text-slate dark:text-slate-dark italic">None noted</li>
              </ul>
            </div>
          </div>
        </div>
      </template>

      <!-- ===== Footer disclaimer ===== -->
      <div class="card p-4 print:border-0 print:shadow-none">
        <p class="text-[10px] text-slate dark:text-slate-dark leading-relaxed">
          Document-grounded comparison generated by PolicyIQ NZ. Every figure is cited to the insurer's published
          policy document. {{ kind === 'life' ? 'Scores reflect policy structure and eligibility only, from a fixed, deterministic rulebook — not a premium quote or financial advice.' : 'This is a fact comparison, not a recommendation.' }}
          Verify against the original document before making decisions.
        </p>
      </div>
    </template>

    <SourceDrawer :source="drawerSource" @close="drawerSource = null" />
  </div>
</template>
