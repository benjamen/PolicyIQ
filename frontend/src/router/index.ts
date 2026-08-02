import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: 'Dashboard', subtitle: 'NZ insurance at a glance' },
    },
    {
      path: '/products',
      name: 'products',
      component: () => import('@/views/ProductsView.vue'),
      meta: { title: 'Products', subtitle: 'Every product, browsable on its own' },
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/CompareView.vue'),
      meta: { title: 'Compare', subtitle: 'Scored, cited, line by line' },
    },
    {
      path: '/report',
      name: 'report',
      component: () => import('@/views/ReportView.vue'),
      meta: { title: 'Report', subtitle: 'Head-to-head comparison' },
    },
    {
      path: '/risk-explorer',
      name: 'risk-explorer',
      component: () => import('@/views/RiskExplorerView.vue'),
      meta: { title: 'Risk Explorer', subtitle: '78 classified risk areas' },
    },
    {
      path: '/insurers',
      name: 'insurers',
      component: () => import('@/views/InsurersView.vue'),
      meta: { title: 'Insurers', subtitle: 'Registry & verified coverage' },
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('@/views/DocumentsView.vue'),
      meta: { title: 'Documents', subtitle: 'Source policies & brochures' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { title: 'Pipeline Health', subtitle: 'Crawler & extraction runs' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: 'Sign in', subtitle: 'Access your account' },
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
      meta: { title: 'Account', subtitle: 'API keys, credits & plan' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'PolicyIQ'} — PolicyIQ NZ`
})
