<script setup lang="ts">
import type { CriterionOut, SourceRef } from '@/api/types'
import Citation from '@/components/Citation.vue'

defineProps<{
  criterion: CriterionOut
  label: string
  blurb: string
}>()

defineEmits<{
  (e: 'open', source: SourceRef): void
}>()

function pct(score: number | null): number {
  return score === null ? 0 : Math.max(0, Math.min(100, score))
}
function barTone(score: number | null): string {
  if (score === null) return 'bg-slate/40 dark:bg-slate-dark/40'
  if (score >= 70) return 'bg-teal dark:bg-teal-dark'
  if (score >= 40) return 'bg-amber dark:bg-amber-dark'
  return 'bg-brick dark:bg-brick-dark'
}
function scoreTone(score: number | null): string {
  if (score === null) return 'text-slate dark:text-slate-dark'
  if (score >= 70) return 'text-teal dark:text-teal-dark'
  if (score >= 40) return 'text-amber dark:text-amber-dark'
  return 'text-brick dark:text-brick-dark'
}
</script>

<template>
  <div class="py-3.5">
    <!-- Header: label + weight + score -->
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-sm font-semibold leading-tight">{{ label }}</span>
          <span
            class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 text-slate dark:text-slate-dark"
            :title="`This criterion counts for ${Math.round(criterion.weight * 100)}% of the overall score`"
          >
            weight {{ Math.round(criterion.weight * 100) }}%
          </span>
        </div>
        <p class="text-[11px] text-slate dark:text-slate-dark mt-0.5 leading-snug">{{ blurb }}</p>
      </div>
      <div class="text-right shrink-0 leading-none">
        <span class="font-mono text-xl font-semibold tabular-nums" :class="scoreTone(criterion.score)">
          {{ criterion.score === null ? '—' : Math.round(criterion.score) }}
        </span>
        <span class="text-[10px] text-slate dark:text-slate-dark ml-0.5">/100</span>
      </div>
    </div>

    <!-- Score bar -->
    <div class="h-1.5 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden mt-2.5">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="barTone(criterion.score)"
        :style="{ width: pct(criterion.score) + '%' }"
      ></div>
    </div>

    <!-- Line-by-line: what the policy says, then why it scored this way -->
    <div class="mt-3 grid grid-cols-[68px_1fr] gap-x-3 gap-y-2 text-xs items-start">
      <span class="text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark pt-0.5 font-medium">Policy says</span>
      <div class="flex items-center justify-between gap-2 flex-wrap">
        <span class="font-mono tabular-nums text-ink/90 dark:text-ink-dark/90">{{ criterion.raw_value }}</span>
        <Citation
          v-if="criterion.source"
          :source="criterion.source"
          compact
          @open="(s) => $emit('open', s)"
        />
        <span v-else class="text-[10px] text-slate dark:text-slate-dark italic">no source on file</span>
      </div>

      <span class="text-[10px] uppercase tracking-wider text-slate dark:text-slate-dark pt-0.5 font-medium">Why</span>
      <p class="leading-relaxed text-ink/75 dark:text-ink-dark/75">{{ criterion.rationale }}</p>
    </div>
  </div>
</template>
