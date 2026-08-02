<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/api/client'
import type { SourceRef, SectionText } from '@/api/types'

const props = defineProps<{
  source: SourceRef | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const section = ref<SectionText | null>(null)

async function load(src: SourceRef) {
  if (!src.document_id) {
    error.value = 'This citation has no linked document.'
    return
  }
  loading.value = true
  error.value = null
  section.value = null
  try {
    section.value = await api.getSectionText(src.document_id, src.page)
  } catch (e) {
    error.value = e instanceof Error && e.message.includes('404')
      ? 'No extracted source text is available for this page yet.'
      : (e instanceof Error ? e.message : 'Failed to load source text.')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.source,
  (src) => {
    if (src) load(src)
  },
  { immediate: true }
)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

function confidencePct(c: number): number {
  return Math.round(c * 100)
}
function confidenceTone(c: number): string {
  if (c >= 0.9) return 'bg-teal dark:bg-teal-dark'
  if (c >= 0.7) return 'bg-amber dark:bg-amber-dark'
  return 'bg-brick dark:bg-brick-dark'
}
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="source" class="fixed inset-0 z-50 flex justify-end">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-ink/40 dark:bg-black/60 backdrop-blur-[2px]" @click="emit('close')"></div>

        <!-- Panel -->
        <aside class="relative w-full max-w-lg h-full bg-paper-raised dark:bg-paper-raised-dark shadow-2xl flex flex-col">
          <!-- Header -->
          <div class="px-5 py-4 border-b border-black/5 dark:border-white/10 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-[10px] font-medium uppercase tracking-wider text-slate dark:text-slate-dark">Source citation</p>
              <h3 class="text-sm font-semibold truncate mt-0.5" :title="source.document">{{ source.document }}</h3>
              <p class="font-mono text-xs text-slate dark:text-slate-dark mt-0.5">
                {{ source.insurer }} · page {{ source.page }}<span v-if="source.paragraph_ref"> · ¶ {{ source.paragraph_ref }}</span>
              </p>
            </div>
            <button
              type="button"
              class="shrink-0 p-1.5 rounded-md text-slate dark:text-slate-dark hover:bg-black/5 dark:hover:bg-white/10 hover:text-ink dark:hover:text-ink-dark transition-colors cursor-pointer"
              aria-label="Close"
              @click="emit('close')"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Confidence meter -->
          <div class="px-5 py-3 border-b border-black/5 dark:border-white/10">
            <div class="flex items-center justify-between text-[10px] text-slate dark:text-slate-dark mb-1.5">
              <span class="uppercase tracking-wider font-medium">Extraction confidence</span>
              <span class="font-mono">{{ confidencePct(source.confidence) }}%</span>
            </div>
            <div class="h-1.5 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="confidenceTone(source.confidence)"
                :style="{ width: confidencePct(source.confidence) + '%' }"
              ></div>
            </div>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-5 py-4">
            <div v-if="loading" class="space-y-3 animate-pulse">
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-11/12"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-full"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-4/5"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-10/12"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-full"></div>
              <div class="h-3 rounded bg-black/5 dark:bg-white/10 w-2/3"></div>
            </div>

            <div v-else-if="error" class="rounded-md border border-amber/30 dark:border-amber-dark/30 bg-amber-soft dark:bg-amber-soft/20 p-4">
              <p class="text-sm text-amber dark:text-amber-dark">{{ error }}</p>
            </div>

            <div v-else-if="section">
              <p class="text-[10px] font-medium uppercase tracking-wider text-slate dark:text-slate-dark mb-2">
                Extracted text — page {{ section.page }}
              </p>
              <p class="font-serif text-sm leading-relaxed whitespace-pre-wrap text-ink/90 dark:text-ink-dark/90">{{ section.text }}</p>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-5 py-3 border-t border-black/5 dark:border-white/10">
            <p class="text-[10px] text-slate dark:text-slate-dark leading-relaxed">
              Extracted automatically from the insurer's published policy document. Verify against the original before making decisions.
            </p>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active aside,
.drawer-leave-active aside {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from aside,
.drawer-leave-to aside {
  transform: translateX(100%);
}
</style>
