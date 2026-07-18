import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    layout?: string
    public?: boolean
    requiresAuth?: boolean
    title?: string
    /** 允许访问的角色；缺省表示登录即可访问 */
    roles?: string[]
  }
}

/** 角色分组：采购方 / 供应商 / 管理端 */
export type RoleGroup = 'buyer' | 'supplier' | 'admin'

const BUYER_ROLES = ['buyer', 'member', 'enterprise_admin']
const SUPPLIER_ROLES = ['supplier']
const ADMIN_ROLES = ['admin', 'platform_admin']

/** 角色 → 分组（未识别角色按采购方处理，保证有可用首页） */
export function roleGroupOf(role?: string): RoleGroup {
  if (role && SUPPLIER_ROLES.includes(role)) return 'supplier'
  if (role && ADMIN_ROLES.includes(role)) return 'admin'
  return 'buyer'
}

/** 各分组的有权限首页（角色校验失败时回退到这里，不报错） */
const GROUP_HOME: Record<RoleGroup, string> = {
  buyer: '/app',
  supplier: '/supplier',
  admin: '/admin/knowledge',
}

export function homePathForRole(role?: string): string {
  return GROUP_HOME[roleGroupOf(role)]
}

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'landing', component: () => import('@/views/LandingView.vue'), meta: { layout: 'blank', public: true, title: '产品介绍' } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { layout: 'blank', public: true, title: '登录' } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { layout: 'blank', public: true, title: '注册' } },

  // 采购方
  { path: '/app', name: 'app', component: () => import('@/views/HomeView.vue'), meta: { requiresAuth: true, title: '经营驾驶舱', roles: BUYER_ROLES } },
  { path: '/products-bom', name: 'products-bom', component: () => import('@/views/ProductsBomView.vue'), meta: { requiresAuth: true, title: '产品与 BOM', roles: BUYER_ROLES } },
  { path: '/shortage-procurement', name: 'shortage-procurement', component: () => import('@/views/ShortageProcurementView.vue'), meta: { requiresAuth: true, title: '缺件与采购', roles: BUYER_ROLES } },
  { path: '/company-chat', name: 'company-chat', component: () => import('@/views/CompanyChat.vue'), meta: { requiresAuth: true, title: '上下游协同问答', roles: BUYER_ROLES } },
  { path: '/company-assistant', name: 'company-assistant', component: () => import('@/views/CompanyAssistant.vue'), meta: { requiresAuth: true, title: '企业内部问答', roles: BUYER_ROLES } },

  { path: '/chat', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { requiresAuth: true, title: '对话寻源', roles: BUYER_ROLES } },
  { path: '/procure/:id', name: 'procure', component: () => import('@/views/ProcureView.vue'), props: true, meta: { requiresAuth: true, title: '寻源工作流', roles: BUYER_ROLES } },
  { path: '/flow', name: 'flow-home', redirect: '/chat' },
  { path: '/spec-confirm', name: 'spec-confirm', redirect: '/chat' },
  { path: '/alternatives', name: 'alternatives', redirect: '/chat' },
  { path: '/supplier-match', name: 'supplier-match', redirect: '/chat' },
  { path: '/rfq-edit', name: 'rfq-edit', redirect: '/chat' },
  { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue'), meta: { requiresAuth: true, title: '历史记录', roles: BUYER_ROLES } },
  { path: '/flow/history', name: 'flow-history', redirect: '/history' },

  // 管理端
  { path: '/admin/knowledge', name: 'admin-knowledge', component: () => import('@/views/AdminKnowledge.vue'), meta: { requiresAuth: true, title: '数据与知识库', roles: ADMIN_ROLES } },
  { path: '/admin/audit', name: 'admin-audit', component: () => import('@/views/P7AdminAudit.vue'), meta: { requiresAuth: true, title: '审核管理', roles: ADMIN_ROLES } },

  // 供应商
  { path: '/supplier', name: 'supplier-dashboard', component: () => import('@/views/supplier/SupplierDashboard.vue'), meta: { requiresAuth: true, title: '供应商工作台', roles: SUPPLIER_ROLES } },
  { path: '/supplier/products', name: 'supplier-products', component: () => import('@/views/supplier/SupplierProducts.vue'), meta: { requiresAuth: true, title: '产品管理', roles: SUPPLIER_ROLES } },
  { path: '/supplier/leads', name: 'supplier-leads', component: () => import('@/views/supplier/SupplierLeads.vue'), meta: { requiresAuth: true, title: '线索管理', roles: SUPPLIER_ROLES } },

  // 404 catch-all（必须最后注册）
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue'), meta: { public: true, title: '页面不存在' } },
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

  // 角色校验：无权限时静默回退到该角色有权限的首页
  const allowed = to.meta.roles
  if (to.meta.requiresAuth && allowed?.length) {
    const role = auth.user?.role
    if (!role || !allowed.includes(role)) {
      return homePathForRole(role)
    }
  }
})

export default router
