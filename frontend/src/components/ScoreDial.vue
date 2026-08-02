<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number | null
  size?: number
}>()

const R = 45
const CIRC = 2 * Math.PI * R

const pct = computed(() => (props.score === null ? 0 : Math.max(0, Math.min(100, props.score))))
const offset = computed(() => CIRC * (1 - pct.value / 100))

const tone = computed(() => {
  if (props.score === null) return 'text-slate dark:text-slate-dark'
  if (props.score >= 70) return 'text-teal dark:text-teal-dark'
  if (props.score >= 40) return 'text-amber dark:text-amber-dark'
  return 'text-brick dark:text-brick-dark'
})
</script>

<template>
  <div class="relative inline-flex items-center justify-center" :style="{ width: (size ?? 72) + 'px', height: (size ?? 72) + 'px' }">
    <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90">
      <circle cx="50" cy="50" :r="R" fill="none" stroke-width="8" class="stroke-black/5 dark:stroke-white/10" />
      <circle
        cx="50" cy="50" :r="R" fill="none" stroke-width="8" stroke-linecap="round"
        class="stroke-current transition-all duration-700 ease-out"
        :class="tone"
        :stroke-dasharray="CIRC"
        :stroke-dashoffset="offset"
      />
    </svg>
    <div class="absolute inset-0 flex flex-col items-center justify-center">
      <span class="font-mono font-semibold tabular-nums leading-none" :class="tone" :style="{ fontSize: (size ?? 72) * 0.26 + 'px' }">
        {{ score === null ? '—' : Math.round(score) }}
      </span>
      <span class="text-[8px] uppercase tracking-wider text-slate dark:text-slate-dark mt-0.5">/ 100</span>
    </div>
  </div>
</template>
