<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { current, dataSource } = useEnterpriseContext()

const pageTitle = computed(() => String(route.meta.title || '经营驾驶舱'))

const mainNav = [
  { to: '/app', icon: 'D', label: '经营驾驶舱' },
  { to: '/products-bom', icon: 'B', label: '产品与 BOM' },
  { to: '/shortage-procurement', icon: '!', label: '缺件与采购' },
  { to: '/company-chat', icon: 'C', label: '上下游协同' },
  { to: '/company-assistant', icon: 'AI', label: '企业内部问答' },
  { to: '/admin/knowledge', icon: 'K', label: '数据与知识库' },
  { to: '/supplier', icon: 'S', label: '供应商工作台' },
  { to: '/admin/audit', icon: 'A', label: '审核管理' },
]

const flowNav = [
  { to: '/flow', icon: 'P', label: '采购寻源流程' },
  { to: '/alternatives', icon: 'R', label: '替代料推荐' },
  { to: '/supplier-match', icon: 'M', label: '供应商匹配' },
  { to: '/rfq-edit', icon: 'Q', label: 'RFQ 编辑' },
]

const sourceLabel = computed(() =>
  dataSource.value === 'api' ? '后端 API' : dataSource.value === 'loading' ? '加载中' : '暂无数据',
)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <RouterLink to="/app" class="brand">
        <span class="brand__mark" />
        <span>
          <span class="brand__name">MatchForge</span>
          <span class="brand__sub">产业链 AI 经营驾驶舱</span>
        </span>
      </RouterLink>
    </div>

    <div class="enterprise-card">
      <span class="enterprise-card__label">当前绑定企业</span>
      <b>{{ current.company.name }}</b>
      <p>{{ current.segment_name || auth.user?.company_segment || '-' }} · {{ current.role || auth.user?.company_role || '-' }}</p>
      <span v-if="auth.user?.is_demo" class="enterprise-badge">演示账号固定视角</span>
      <p class="enterprise-source">数据来源：{{ sourceLabel }}</p>
    </div>

    <nav class="sidebar__nav" aria-label="主导航">
      <RouterLink v-for="item in mainNav" :key="item.to" :to="item.to" class="nav__link">
        <span class="nav__icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar__section">
      <p class="sidebar__label">保留流程入口</p>
      <RouterLink v-for="item in flowNav" :key="item.to" :to="item.to" class="nav__link">
        <span class="nav__icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </div>

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
  width: 256px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  background: rgba(10, 11, 15, 0.94);
  border-right: 1px solid var(--border-default);
  backdrop-filter: blur(18px);
}
.sidebar__brand { padding: var(--space-1) var(--space-1) var(--space-3); }
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-primary);
}
.brand__mark {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
}
.brand__name { display: block; font-weight: 700; font-size: var(--font-size-md); line-height: 1.1; }
.brand__sub { display: block; margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.enterprise-card {
  padding: var(--space-3);
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--bg-1);
}
.enterprise-card__label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.enterprise-card b {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.35;
}
.enterprise-card p {
  margin-top: 7px;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.enterprise-badge {
  display: inline-flex;
  align-items: center;
  margin-top: 8px;
  padding: 3px 7px;
  color: #d9ddff;
  border: 1px solid rgba(129, 140, 248, 0.45);
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.13);
  font-size: 11px;
  font-weight: 700;
}
.enterprise-source {
  margin-top: 4px !important;
  color: var(--accent) !important;
  font-weight: 600;
}
.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0 var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.nav__link {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 10px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}
.nav__link:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.04); }
.nav__link.router-link-exact-active {
  color: var(--text-primary);
  background: var(--bg-2);
  box-shadow: inset 0 0 0 1px var(--border-subtle);
}
.nav__icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.sidebar__section { padding-top: var(--space-2); }
.sidebar__label {
  margin-bottom: var(--space-2);
  padding: 0 10px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.sidebar__notice {
  margin-top: auto;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
}
.sidebar__notice b {
  display: block;
  margin-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.sidebar__notice p { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.6; }
.topbar {
  position: fixed;
  top: 0;
  left: 256px;
  right: 0;
  z-index: 50;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 0 var(--space-5);
  background: rgba(10, 11, 15, 0.78);
  border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(18px);
}
.topbar__left,
.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}
.topbar__crumb,
.topbar__slash { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.topbar__title { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.user { display: flex; align-items: center; gap: var(--space-2); }
.user__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-xs);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.user__name { font-size: var(--font-size-sm); color: var(--text-secondary); }
.logout {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  padding: 5px 10px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}
.logout:hover { color: var(--danger); background: var(--danger-soft); }
@media (max-width: 920px) {
  .sidebar {
    right: 0;
    bottom: auto;
    width: auto;
    min-height: 48px;
    padding: var(--space-2) var(--space-3);
    flex-direction: row;
    align-items: center;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
  }
  .sidebar__brand { padding: 0; }
  .brand__sub,
  .enterprise-card,
  .sidebar__section,
  .sidebar__notice { display: none; }
  .sidebar__nav {
    flex-direction: row;
    padding: 0;
    margin-left: var(--space-4);
    border-top: none;
  }
  .topbar { top: 48px; left: 0; height: 56px; }
}
@media (max-width: 640px) {
  .brand__name,
  .topbar__crumb,
  .topbar__slash,
  .user__name { display: none; }
  .topbar { padding: 0 var(--space-3); }
}
</style>
