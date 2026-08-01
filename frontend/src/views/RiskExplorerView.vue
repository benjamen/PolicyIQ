<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RiskArea, CoverageStatus } from '@/api/types'

// Static taxonomy from backend (78 nodes, 11 top-level)
const TOP_LEVEL_AREAS: RiskArea[] = [
  { code: 'property_damage', name: 'Property Damage', parent_code: null, description: 'Damage to buildings and structures', sort_order: 1 },
  { code: 'contents_damage', name: 'Contents & Belongings', parent_code: null, description: 'Loss or damage to personal possessions', sort_order: 2 },
  { code: 'liability', name: 'Liability', parent_code: null, description: 'Legal liability to third parties', sort_order: 3 },
  { code: 'personal_risk', name: 'Personal Risk', parent_code: null, description: 'Life, TPD, trauma, and income protection', sort_order: 4 },
  { code: 'medical', name: 'Medical & Health', parent_code: null, description: 'Health insurance and medical costs', sort_order: 5 },
  { code: 'motor', name: 'Motor Vehicle', parent_code: null, description: 'Vehicle damage and third-party motor', sort_order: 6 },
  { code: 'travel', name: 'Travel', parent_code: null, description: 'Travel insurance and trip protection', sort_order: 7 },
  { code: 'pet', name: 'Pet', parent_code: null, description: 'Veterinary and pet liability', sort_order: 8 },
  { code: 'landlord', name: 'Landlord & Rental', parent_code: null, description: 'Rental property and landlord risks', sort_order: 9 },
  { code: 'marine', name: 'Marine & Watercraft', parent_code: null, description: 'Boats, jet skis, and marine craft', sort_order: 10 },
  { code: 'business', name: 'Business', parent_code: null, description: 'Commercial and business interruption', sort_order: 11 },
]

const CHILDREN: Record<string, RiskArea[]> = {
  property_damage: [
    { code: 'fire', name: 'Fire & Explosion', parent_code: 'property_damage', description: null, sort_order: 1 },
    { code: 'storm', name: 'Storm & Wind', parent_code: 'property_damage', description: null, sort_order: 2 },
    { code: 'flood', name: 'Flood', parent_code: 'property_damage', description: null, sort_order: 3 },
    { code: 'earthquake', name: 'Earthquake & Tsunami', parent_code: 'property_damage', description: null, sort_order: 4 },
    { code: 'water_damage', name: 'Escape of Water', parent_code: 'property_damage', description: null, sort_order: 5 },
    { code: 'theft_property', name: 'Theft & Burglary', parent_code: 'property_damage', description: null, sort_order: 6 },
    { code: 'subsidence', name: 'Subsidence & Landslip', parent_code: 'property_damage', description: null, sort_order: 7 },
  ],
  contents_damage: [
    { code: 'contents_theft', name: 'Theft of Contents', parent_code: 'contents_damage', description: null, sort_order: 1 },
    { code: 'accidental_damage', name: 'Accidental Damage', parent_code: 'contents_damage', description: null, sort_order: 2 },
    { code: 'valuables', name: 'Specified Valuables', parent_code: 'contents_damage', description: null, sort_order: 3 },
  ],
  liability: [
    { code: 'public_liability', name: 'Public Liability', parent_code: 'liability', description: null, sort_order: 1 },
    { code: 'tenant_liability', name: 'Tenant Liability', parent_code: 'liability', description: null, sort_order: 2 },
  ],
  personal_risk: [
    { code: 'death', name: 'Death / Life Cover', parent_code: 'personal_risk', description: null, sort_order: 1 },
    { code: 'tpd', name: 'Total & Permanent Disability', parent_code: 'personal_risk', description: null, sort_order: 2 },
    { code: 'trauma', name: 'Trauma / Critical Illness', parent_code: 'personal_risk', description: null, sort_order: 3 },
    { code: 'income_protection', name: 'Income Protection', parent_code: 'personal_risk', description: null, sort_order: 4 },
  ],
  medical: [
    { code: 'hospital_cover', name: 'Hospital & Surgical', parent_code: 'medical', description: null, sort_order: 1 },
    { code: 'specialist', name: 'Specialist Consultations', parent_code: 'medical', description: null, sort_order: 2 },
    { code: 'dental', name: 'Dental', parent_code: 'medical', description: null, sort_order: 3 },
  ],
  motor: [
    { code: 'collision', name: 'Collision Damage', parent_code: 'motor', description: null, sort_order: 1 },
    { code: 'third_party_motor', name: 'Third Party Property', parent_code: 'motor', description: null, sort_order: 2 },
    { code: 'theft_motor', name: 'Theft of Vehicle', parent_code: 'motor', description: null, sort_order: 3 },
  ],
  travel: [
    { code: 'trip_cancellation', name: 'Trip Cancellation', parent_code: 'travel', description: null, sort_order: 1 },
    { code: 'medical_overseas', name: 'Overseas Medical', parent_code: 'travel', description: null, sort_order: 2 },
    { code: 'baggage', name: 'Baggage & Personal Effects', parent_code: 'travel', description: null, sort_order: 3 },
  ],
  pet: [
    { code: 'vet_fees', name: 'Veterinary Fees', parent_code: 'pet', description: null, sort_order: 1 },
    { code: 'pet_liability', name: 'Pet Liability', parent_code: 'pet', description: null, sort_order: 2 },
  ],
  landlord: [
    { code: 'rent_loss', name: 'Loss of Rent', parent_code: 'landlord', description: null, sort_order: 1 },
    { code: 'tenant_damage', name: 'Malicious Tenant Damage', parent_code: 'landlord', description: null, sort_order: 2 },
  ],
  marine: [
    { code: 'hull_damage', name: 'Hull & Machinery', parent_code: 'marine', description: null, sort_order: 1 },
    { code: 'marine_liability', name: 'Marine Liability', parent_code: 'marine', description: null, sort_order: 2 },
  ],
  business: [
    { code: 'business_interruption', name: 'Business Interruption', parent_code: 'business', description: null, sort_order: 1 },
    { code: 'commercial_property', name: 'Commercial Property', parent_code: 'business', description: null, sort_order: 2 },
    { code: 'cyber', name: 'Cyber & Data Breach', parent_code: 'business', description: null, sort_order: 3 },
  ],
}

const selectedArea = ref<string | null>(null)
const searchQuery = ref('')

const filteredAreas = computed(() => {
  if (!searchQuery.value) return TOP_LEVEL_AREAS
  const q = searchQuery.value.toLowerCase()
  return TOP_LEVEL_AREAS.filter(a =>
    a.name.toLowerCase().includes(q) ||
    (CHILDREN[a.code] ?? []).some(c => c.name.toLowerCase().includes(q))
  )
})

const children = computed(() =>
  selectedArea.value ? (CHILDREN[selectedArea.value] ?? []) : []
)

const totalAreas = computed(() =>
  TOP_LEVEL_AREAS.length + Object.values(CHILDREN).reduce((s, c) => s + c.length, 0)
)

const coverageBadgeClass = (status: CoverageStatus): string => {
  const map: Record<CoverageStatus, string> = {
    covered: 'badge-covered',
    excluded: 'badge-excluded',
    limited: 'badge-limited',
    sub_limited: 'badge-limited',
    silent: 'badge-silent',
  }
  return map[status]
}
void coverageBadgeClass
</script>

<template>
  <div class="space-y-6 max-w-6xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="section-title">Risk Area Taxonomy</h2>
        <p class="text-xs text-slate dark:text-slate-dark mt-0.5">{{ totalAreas }} classified risk areas across {{ TOP_LEVEL_AREAS.length }} categories</p>
      </div>
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search risk areas..."
        class="input-field w-full sm:w-64"
      />
    </div>

    <!-- Area Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <button
        v-for="area in filteredAreas"
        :key="area.code"
        @click="selectedArea = selectedArea === area.code ? null : area.code"
        class="card p-4 text-left transition-all duration-150 cursor-pointer hover:shadow-md"
        :class="selectedArea === area.code ? 'ring-2 ring-teal/40 dark:ring-teal-dark/40' : ''"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold">{{ area.name }}</h3>
          <span class="badge-covered">{{ (CHILDREN[area.code] ?? []).length }}</span>
        </div>
        <p class="text-xs text-slate dark:text-slate-dark mt-1">{{ area.description }}</p>
        <div class="flex flex-wrap gap-1 mt-3">
          <span
            v-for="child in (CHILDREN[area.code] ?? []).slice(0, 3)"
            :key="child.code"
            class="text-[10px] px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/5 text-slate dark:text-slate-dark"
          >
            {{ child.name }}
          </span>
          <span v-if="(CHILDREN[area.code] ?? []).length > 3" class="text-[10px] text-slate dark:text-slate-dark">
            +{{ (CHILDREN[area.code] ?? []).length - 3 }} more
          </span>
        </div>
      </button>
    </div>

    <!-- Expanded children -->
    <div v-if="selectedArea && children.length > 0" class="card overflow-hidden">
      <div class="px-5 py-4 border-b border-black/5 dark:border-white/10 flex items-center justify-between">
        <h3 class="text-sm font-semibold">
          {{ TOP_LEVEL_AREAS.find(a => a.code === selectedArea)?.name }} — Sub-areas
        </h3>
        <button @click="selectedArea = null" class="text-xs text-slate dark:text-slate-dark hover:text-ink dark:hover:text-ink-dark cursor-pointer">
          Collapse
        </button>
      </div>
      <div class="divide-y divide-black/[0.03] dark:divide-white/[0.04]">
        <div v-for="child in children" :key="child.code" class="flex items-center justify-between px-5 py-3">
          <div>
            <p class="text-sm font-medium">{{ child.name }}</p>
            <p class="text-xs text-slate dark:text-slate-dark font-mono">{{ child.code }}</p>
          </div>
          <span class="badge-silent">awaiting data</span>
        </div>
      </div>
    </div>

    <!-- Info card -->
    <div class="card p-5">
      <h3 class="text-sm font-semibold mb-2">How Risk Areas Work</h3>
      <p class="text-xs text-slate dark:text-slate-dark leading-relaxed">
        Each risk area maps to specific <strong>risk events</strong> that insurers may cover, exclude, or limit.
        The coverage matrix cross-references every insurer's policy documents against this taxonomy,
        producing a comparable grid of <span class="badge-covered mx-1">covered</span>
        <span class="badge-excluded mx-1">excluded</span>
        <span class="badge-limited mx-1">limited</span>
        <span class="badge-silent mx-1">silent</span> statuses per event per insurer.
      </p>
    </div>
  </div>
</template>
