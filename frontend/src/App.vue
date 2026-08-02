<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useAuth } from '@/composables/useAuth'

const route = useRoute()
const { theme, cycle } = useTheme()
const { isAuthenticated, user } = useAuth()

const nav = [
  { path: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { path: '/compare', label: 'Compare', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { path: '/risk-explorer', label: 'Risk Explorer', icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { path: '/insurers', label: 'Insurers', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
  { path: '/documents', label: 'Documents', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
]

const navGroups = [
  { label: 'Overview', items: nav.slice(0, 3) },
  { label: 'Data & Sources', items: nav.slice(3) },
]

const themeIcon = {
  light: 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
  dark: 'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z',
  system: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
}
</script>

<template>
  <div class="flex h-dvh overflow-hidden">
    <!-- Sidebar -->
    <aside class="hidden md:flex flex-col w-56 border-r border-black/5 dark:border-white/10 bg-paper-raised dark:bg-paper-raised-dark">
      <!-- Logo -->
      <div class="flex items-center gap-2.5 px-5 h-14 border-b border-black/5 dark:border-white/10">
        <div class="w-7 h-7 rounded-md bg-gradient-to-br from-teal to-[#084c3e] dark:from-teal-dark dark:to-[#0f5c4b] flex items-center justify-center shadow-sm">
          <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <span class="font-semibold text-sm tracking-tight">PolicyIQ<span class="text-teal dark:text-teal-dark">.nz</span></span>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 py-2 px-3 overflow-y-auto">
        <template v-for="group in navGroups" :key="group.label">
          <p class="nav-section-label">{{ group.label }}</p>
          <div class="space-y-0.5">
            <router-link
              v-for="item in group.items"
              :key="item.path"
              :to="item.path"
              class="relative flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150"
              :class="route.path === item.path
                ? 'bg-teal-soft dark:bg-teal-soft-dark text-teal dark:text-teal-dark'
                : 'text-slate dark:text-slate-dark hover:bg-black/5 dark:hover:bg-white/5 hover:text-ink dark:hover:text-ink-dark'"
            >
              <span
                v-if="route.path === item.path"
                class="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-teal dark:bg-teal-dark"
              ></span>
              <svg class="w-[18px] h-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
              </svg>
              {{ item.label }}
            </router-link>
          </div>
        </template>
      </nav>

      <!-- Footer -->
      <div class="px-4 py-3 border-t border-black/5 dark:border-white/10 space-y-2">
        <div class="flex items-center gap-2 px-2 py-1.5 rounded-md bg-teal-soft/60 dark:bg-teal-soft-dark/60">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal dark:bg-teal-dark opacity-60"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-teal dark:bg-teal-dark"></span>
          </span>
          <p class="text-[11px] font-medium text-teal dark:text-teal-dark">Every claim cited</p>
        </div>
        <p class="px-2 text-[11px] text-slate dark:text-slate-dark font-mono">PolicyIQ NZ · v1.0.0</p>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top bar -->
      <header class="flex items-center justify-between h-14 px-4 md:px-6 border-b border-black/5 dark:border-white/10 bg-paper-raised/80 dark:bg-paper-raised-dark/80 backdrop-blur-sm">
        <div class="flex items-center gap-3 min-w-0">
          <div class="leading-tight min-w-0">
            <h1 class="text-sm font-semibold truncate">{{ route.meta.title }}</h1>
            <p v-if="route.meta.subtitle" class="text-[11px] text-slate dark:text-slate-dark truncate">{{ route.meta.subtitle }}</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- Account / Login -->
          <router-link
            v-if="isAuthenticated"
            to="/account"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            title="Account"
          >
            <div class="w-6 h-6 rounded-full bg-teal-soft dark:bg-teal-soft-dark flex items-center justify-center">
              <span class="text-[11px] font-bold text-teal dark:text-teal-dark">{{ (user?.name || user?.email || '?')[0].toUpperCase() }}</span>
            </div>
            <span class="hidden sm:block text-xs font-medium">{{ user?.credit_balance ?? 0 }} credits</span>
          </router-link>
          <router-link
            v-else
            to="/login"
            class="px-3 py-1.5 rounded-lg bg-teal dark:bg-teal-dark text-white text-xs font-medium hover:opacity-90 transition-opacity"
          >
            Sign in
          </router-link>

          <!-- Theme toggle -->
          <button
            @click="cycle"
            class="p-2 rounded-md hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            :title="`Theme: ${theme}`"
          >
            <svg class="w-[18px] h-[18px] text-slate dark:text-slate-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" :d="themeIcon[theme]" />
            </svg>
          </button>
        </div>
      </header>

      <!-- Mobile nav -->
      <nav class="md:hidden flex border-b border-black/5 dark:border-white/10 bg-paper-raised dark:bg-paper-raised-dark overflow-x-auto">
        <router-link
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors"
          :class="route.path === item.path
            ? 'border-teal dark:border-teal-dark text-teal dark:text-teal-dark'
            : 'border-transparent text-slate dark:text-slate-dark'"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-4 md:p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>
