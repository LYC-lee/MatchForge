import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'landing', component: () => import('@/views/LandingView.vue'), meta: { layout: 'blank', public: true, title: '产品介绍' } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { layout: 'blank', public: true, title: '登录' } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { layout: 'blank', public: true, title: '注册' } },

  { path: '/app', name: 'app', component: () => import('@/views/HomeView.vue'), meta: { requiresAuth: true, title: '经营驾驶舱' } },
  { path: '/products-bom', name: 'products-bom', component: () => import('@/views/ProductsBomView.vue'), meta: { requiresAuth: true, title: '产品与 BOM' } },
  { path: '/shortage-procurement', name: 'shortage-procurement', component: () => import('@/views/ShortageProcurementView.vue'), meta: { requiresAuth: true, title: '缺件与采购' } },
  { path: '/company-chat', name: 'company-chat', component: () => import('@/views/CompanyChat.vue'), meta: { requiresAuth: true, title: '上下游协同问答' } },
  { path: '/company-assistant', name: 'company-assistant', component: () => import('@/views/CompanyAssistant.vue'), meta: { requiresAuth: true, title: '企业内部问答' } },
  { path: '/admin/knowledge', name: 'admin-knowledge', component: () => import('@/views/AdminKnowledge.vue'), meta: { requiresAuth: true, title: '数据与知识库' } },

  { path: '/chat', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { requiresAuth: true, title: '对话寻源' } },
  { path: '/procure/:id', name: 'procure', component: () => import('@/views/ProcureView.vue'), props: true, meta: { requiresAuth: true, title: '寻源工作流' } },
  { path: '/flow', name: 'flow-home', component: () => import('@/views/P1Home.vue'), meta: { requiresAuth: true, title: 'AI 寻源' } },
  { path: '/spec-confirm', name: 'spec-confirm', component: () => import('@/views/P2SpecConfirm.vue'), meta: { requiresAuth: true, title: '规格确认' } },
  { path: '/alternatives', name: 'alternatives', component: () => import('@/views/P3Alternatives.vue'), meta: { requiresAuth: true, title: '替代料结果' } },
  { path: '/supplier-match', name: 'supplier-match', component: () => import('@/views/P4SupplierMatch.vue'), meta: { requiresAuth: true, title: '供应商匹配' } },
  { path: '/rfq-edit', name: 'rfq-edit', component: () => import('@/views/P5RfqEdit.vue'), meta: { requiresAuth: true, title: '询价单编辑' } },
  { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue'), meta: { requiresAuth: true, title: '历史记录' } },
  { path: '/flow/history', name: 'flow-history', component: () => import('@/views/P6History.vue'), meta: { requiresAuth: true, title: '流程历史记录' } },
  { path: '/admin/audit', name: 'admin-audit', component: () => import('@/views/P7AdminAudit.vue'), meta: { requiresAuth: true, title: '运营审核' } },

  { path: '/supplier', name: 'supplier-dashboard', component: () => import('@/views/supplier/SupplierDashboard.vue'), meta: { requiresAuth: true, title: '供应商工作台' } },
  { path: '/supplier/products', name: 'supplier-products', component: () => import('@/views/supplier/SupplierProducts.vue'), meta: { requiresAuth: true, title: '产品管理' } },
  { path: '/supplier/leads', name: 'supplier-leads', component: () => import('@/views/supplier/SupplierLeads.vue'), meta: { requiresAuth: true, title: '线索管理' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to) => {
  document.title = `${String(to.meta.title || 'MatchForge')} - MatchForge 智配`

  const auth = useAuthStore()
  if (to.meta.requiresAuth && !(await auth.validateSession())) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

export default router
