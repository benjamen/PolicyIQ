<script setup lang="ts">
import type { SourceRef } from '@/api/types'

defineProps<{
  source: SourceRef
  compact?: boolean
}>()

defineEmits<{
  (e: 'open', source: SourceRef): void
}>()

function confidenceTone(c: number): string {
  if (c >= 0.9) return 'text-teal dark:text-teal-dark'
  if (c >= 0.7) return 'text-amber dark:text-amber-dark'
  return 'text-brick dark:text-brick-dark'
}
</script>

<template>
  <button
    type="button"
    class="group inline-flex items-center gap-1.5 rounded-md border border-black/10 dark:border-white/15 bg-black/[0.03] dark:bg-white/[0.04] px-2 py-1 text-left transition-colors hover:border-teal/40 dark:hover:border-teal-dark/40 hover:bg-teal-soft dark:hover:bg-teal-soft-dark cursor-pointer"
    :title="source.document"
    @click.stop="$emit('open', source)"
  >
    <svg class="w-3 h-3 text-slate dark:text-slate-dark group-hover:text-teal dark:group-hover:text-teal-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
    <span class="font-mono text-[10px] leading-none text-slate dark:text-slate-dark group-hover:text-ink dark:group-hover:text-ink-dark">
      p.{{ source.page }}<span v-if="source.paragraph_ref"> · {{ source.paragraph_ref }}</span>
    </span>
    <span
      v-if="!compact"
      class="font-mono text-[10px] leading-none"
      :class="confidenceTone(source.confidence)"
    >{{ Math.round(source.confidence * 100) }}%</span>
  </button>
</template>
