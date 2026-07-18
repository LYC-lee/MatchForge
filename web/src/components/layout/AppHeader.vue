<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { homePathForRole, roleGroupOf, type RoleGroup } from '@/router'
import ThemeToggle from '@/components/ui/ThemeToggle.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { current, dataSource } = useEnterpriseContext()

// 面包屑：未知路径回退为「首页」
const pageTitle = computed(() => String(route.meta.title || '首页'))

interface NavItem {
  to: string
  icon: string
  label: string
  group: RoleGroup
}

// 导航按角色分组过滤：采购方 / 供应商 / 管理端
const NAV: NavItem[] = [
  { to: '/app', icon: 'D', label: '经营驾驶舱', group: 'buyer' },
  { to: '/chat', icon: '🔍', label: '对话寻源', group: 'buyer' },
  { to: '/history', icon: 'H', label: '历史记录', group: 'buyer' },
  { to: '/products-bom', icon: 'B', label: '产品与 BOM', group: 'buyer' },
  { to: '/shortage-procurement', icon: '!', label: '缺件与采购', group: 'buyer' },
  { to: '/company-chat', icon: 'C', label: '协同问答', group: 'buyer' },
  { to: '/company-assistant', icon: 'AI', label: '企业问答', group: 'buyer' },
  { to: '/supplier', icon: 'S', label: '工作台', group: 'supplier' },
  { to: '/supplier/products', icon: 'P', label: '产品管理', group: 'supplier' },
  { to: '/supplier/leads', icon: 'L', label: '线索管理', group: 'supplier' },
  { to: '/admin/knowledge', icon: 'K', label: '数据与知识库', group: 'admin' },
  { to: '/admin/audit', icon: 'A', label: '审核管理', group: 'admin' },
]

const GROUP_LABEL: Record<RoleGroup, string> = {
  buyer: '采购方',
  supplier: '供应商',
  admin: '管理端',
}

const roleGroup = computed<RoleGroup>(() => roleGroupOf(auth.user?.role))
const mainNav = computed(() => NAV.filter((item) => item.group === roleGroup.value))
const homePath = computed(() => homePathForRole(auth.user?.role))

const sourceLabel = computed(() =>
  dataSource.value === 'api' ? '后端 API' : dataSource.value === 'loading' ? '加载中' : '暂无数据',
)

// ≤920px 汉堡菜单
const menuOpen = ref(false)
watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
  },
)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <RouterLink :to="homePath" class="brand">
        <span class="brand__mark" />
        <span>
          <span class="brand__name">MatchForge</span>
          <span class="brand__sub">产业链 AI 经营驾驶舱</span>
        </span>
      </RouterLink>
      <button
        class="nav-toggle"
        :aria-expanded="menuOpen"
        aria-controls="sidebar-nav"
        aria-label="打开导航菜单"
        @click="menuOpen = !menuOpen"
      >
        <span class="nav-toggle__bars" aria-hidden="true" />
      </button>
    </div>

    <div class="enterprise-card">
      <span class="enterprise-card__label">当前绑定企业</span>
      <b>{{ current.company.name }}</b>
      <p>{{ current.segment_name || auth.user?.company_segment || '-' }} · {{ current.role || auth.user?.company_role || '-' }}</p>
      <span v-if="auth.user?.is_demo" class="enterprise-badge">演示账号固定视角</span>
      <p class="enterprise-source">数据来源：{{ sourceLabel }}</p>
    </div>

    <nav id="sidebar-nav" class="sidebar__nav" :class="{ 'sidebar__nav--open': menuOpen }" aria-label="主导航">
      <p class="sidebar__label">{{ GROUP_LABEL[roleGroup] }}</p>
      <RouterLink v-for="item in mainNav" :key="item.to" :to="item.to" class="nav__link">
        <span class="nav__icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar__notice">
      <b>数据边界</b>
      <p>经营驾驶舱优先读取真实后端接口；问答页面不再生成本地固定业务回答。</p>
    </div>
  </aside>

  <header class="topbar">
    <div class="topbar__left">
      <span class="topbar__crumb">{{ current.company.name }}</span>
      <span class="topbar__slash">/</span>
      <span class="topbar__title">{{ pageTitle }}</span>
    </div>
    <div class="topbar__right">
      <ThemeToggle />
      <span v-if="auth.user" class="user">
        <span class="user__avatar">{{ auth.user.name.slice(0, 1).toUpperCase() }}</span>
        <span class="user__name">{{ auth.user.name }}</span>
      </span>
      <button class="logout" @click="logout">退出</button>
    </div>
  </header>
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-w);
  z-index: var(--z-sticky);
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  background: var(--bg-canvas);
  border-right: 1px solid var(--border-default);
}
.sidebar__brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-1) var(--space-3);
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-primary);
}
.brand__mark {
  width: var(--space-6);
  height: var(--space-6);
  flex: 0 0 auto;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
}
.brand__name {
  display: block;
  font-weight: 700;
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
}
.brand__sub {
  display: block;
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
}
.enterprise-card {
  padding: var(--space-3);
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
}
.enterprise-card__label {
  display: block;
  margin-bottom: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
}
.enterprise-card b {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.enterprise-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.enterprise-badge {
  display: inline-flex;
  align-items: center;
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-2);
  color: var(--accent-text);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-full);
  background: var(--accent-soft);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
}
.enterprise-source {
  color: var(--accent-text);
  font-weight: 600;
}
.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0 var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.sidebar__label {
  margin-bottom: var(--space-2);
  padding: 0 var(--space-3);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.nav__link {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.nav__link:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.nav__link.router-link-exact-active {
  color: var(--text-primary);
  background: var(--bg-subtle);
  box-shadow: inset 0 0 0 1px var(--border-subtle);
}
.nav__icon {
  width: var(--space-5);
  height: var(--space-5);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.sidebar__notice {
  margin-top: auto;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
}
.sidebar__notice b {
  display: block;
  margin-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.sidebar__notice p {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.nav-toggle {
  display: none;
  width: var(--space-6);
  height: var(--space-6);
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.nav-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.nav-toggle__bars,
.nav-toggle__bars::before,
.nav-toggle__bars::after {
  display: block;
  width: var(--space-4);
  height: 2px;
  border-radius: var(--radius-full);
  background: currentColor;
}
.nav-toggle__bars {
  position: relative;
}
.nav-toggle__bars::before,
.nav-toggle__bars::after {
  content: '';
  position: absolute;
  left: 0;
}
.nav-toggle__bars::before {
  top: calc(-1 * var(--space-1) - 1px);
}
.nav-toggle__bars::after {
  top: calc(var(--space-1) + 1px);
}
.topbar {
  position: fixed;
  top: 0;
  left: var(--sidebar-w);
  right: 0;
  z-index: var(--z-sticky);
  height: var(--header-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 0 var(--space-5);
  background: var(--bg-canvas);
  border-bottom: 1px solid var(--border-default);
}
.topbar__left,
.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}
.topbar__crumb,
.topbar__slash {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.topbar__title {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.user__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.user__name {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
}
.logout {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-tertiary);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.logout:hover {
  color: var(--danger);
  background: var(--danger-soft);
}

/* ≤920px：侧栏折叠为顶部横条，导航收进汉堡菜单 */
@media (max-width: 920px) {
  .sidebar {
    right: 0;
    bottom: auto;
    width: auto;
    height: var(--header-h);
    padding: 0 var(--space-3);
    flex-direction: row;
    align-items: center;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
  }
  .sidebar__brand {
    padding: 0;
    width: 100%;
  }
  .brand__sub,
  .enterprise-card,
  .sidebar__notice {
    display: none;
  }
  .nav-toggle {
    display: inline-flex;
  }
  .sidebar__nav {
    display: none;
    position: absolute;
    top: var(--header-h);
    left: 0;
    right: 0;
    padding: var(--space-2);
    background: var(--bg-elevated);
    border-bottom: 1px solid var(--border-default);
    box-shadow: var(--shadow-md);
  }
  .sidebar__nav--open {
    display: flex;
  }
  .topbar {
    top: var(--header-h);
    left: 0;
  }
}
@media (max-width: 640px) {
  .brand__name,
  .topbar__crumb,
  .topbar__slash,
  .user__name {
    display: none;
  }
  .topbar {
    padding: 0 var(--space-3);
  }
}
</style>
