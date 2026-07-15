import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'landing',
    component: () => import('@/views/LandingView.vue'),
    meta: { layout: 'blank', public: true, title: '产品介绍' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { layout: 'blank', public: true, title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { layout: 'blank', public: true, title: '注册' },
  },
  // ── 采购端 (buyer) ──
  {
    path: '/app',
    name: 'app',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '产品功能' },
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '对话寻源' },
  },
  {
    path: '/procure/:id',
    name: 'procure',
    component: () => import('@/views/ProcureView.vue'),
    props: true,
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '寻源工作流' },
  },
  {
    path: '/flow',
    name: 'flow-home',
    component: () => import('@/views/P1Home.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: 'AI 寻源' },
  },
  {
    path: '/spec-confirm',
    name: 'spec-confirm',
    component: () => import('@/views/P2SpecConfirm.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '规格确认' },
  },
  {
    path: '/alternatives',
    name: 'alternatives',
    component: () => import('@/views/P3Alternatives.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '替代料结果' },
  },
  {
    path: '/supplier-match',
    name: 'supplier-match',
    component: () => import('@/views/P4SupplierMatch.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '供应商匹配' },
  },
  {
    path: '/rfq-edit',
    name: 'rfq-edit',
    component: () => import('@/views/P5RfqEdit.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '询价单编辑' },
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '历史记录' },
  },
  {
    path: '/flow/history',
    name: 'flow-history',
    component: () => import('@/views/P6History.vue'),
    meta: { requiresAuth: true, roles: ['buyer', 'admin'], title: '流程历史记录' },
  },
  // ── 供应商端 (supplier) ──
  {
    path: '/supplier',
    name: 'supplier-dashboard',
    component: () => import('@/views/supplier/SupplierDashboard.vue'),
    meta: { requiresAuth: true, roles: ['supplier', 'admin'], title: '供应商工作台' },
  },
  {
    path: '/supplier/products',
    name: 'supplier-products',
    component: () => import('@/views/supplier/SupplierProducts.vue'),
    meta: { requiresAuth: true, roles: ['supplier', 'admin'], title: '产品管理' },
  },
  {
    path: '/supplier/leads',
    name: 'supplier-leads',
    component: () => import('@/views/supplier/SupplierLeads.vue'),
    meta: { requiresAuth: true, roles: ['supplier', 'admin'], title: '线索管理' },
  },
  // ── 运营端 (admin) ──
  {
    path: '/admin/audit',
    name: 'admin-audit',
    component: () => import('@/views/P7AdminAudit.vue'),
    meta: { requiresAuth: true, roles: ['admin'], title: '运营审核' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// ── 路由守卫: 认证 + 角色 ──
router.beforeEach((to) => {
  document.title = `${String(to.meta.title || 'MatchForge')} - MatchForge 智配`

  const auth = useAuthStore()
  if (to.meta.public) return true

  if (!auth.validateSession()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(auth.role)) {
    // 角色不匹配 → 跳转到对应首页
    if (auth.role === 'buyer') return { name: 'app' }
    if (auth.role === 'supplier') return { name: 'supplier-dashboard' }
    if (auth.role === 'admin') return { name: 'app' }
    return { name: 'landing' }
  }

  return true
})

export default router
