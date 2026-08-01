import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: 'Dashboard' },
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/CompareView.vue'),
      meta: { title: 'Compare' },
    },
    {
      path: '/risk-explorer',
      name: 'risk-explorer',
      component: () => import('@/views/RiskExplorerView.vue'),
      meta: { title: 'Risk Explorer' },
    },
    {
      path: '/insurers',
      name: 'insurers',
      component: () => import('@/views/InsurersView.vue'),
      meta: { title: 'Insurers' },
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('@/views/DocumentsView.vue'),
      meta: { title: 'Documents' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { title: 'Pipeline Health' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'PolicyIQ'} — PolicyIQ NZ`
})
