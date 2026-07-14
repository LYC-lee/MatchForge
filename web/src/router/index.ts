import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/P1Home.vue'),
    meta: { title: 'AI 寻源' },
  },
  {
    path: '/spec-confirm',
    name: 'spec-confirm',
    component: () => import('@/views/P2SpecConfirm.vue'),
    meta: { title: '规格确认' },
  },
  {
    path: '/alternatives',
    name: 'alternatives',
    component: () => import('@/views/P3Alternatives.vue'),
    meta: { title: '替代料结果' },
  },
  {
    path: '/supplier-match',
    name: 'supplier-match',
    component: () => import('@/views/P4SupplierMatch.vue'),
    meta: { title: '供应商匹配' },
  },
  {
    path: '/rfq-edit',
    name: 'rfq-edit',
    component: () => import('@/views/P5RfqEdit.vue'),
    meta: { title: '询价单编辑' },
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/P6History.vue'),
    meta: { title: '历史记录' },
  },
  {
    path: '/admin/audit',
    name: 'admin-audit',
    component: () => import('@/views/P7AdminAudit.vue'),
    meta: { title: '运营审核' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title} - MatchForge 智配`
})

export default router