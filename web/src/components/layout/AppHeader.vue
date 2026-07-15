<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const pageTitle = computed(() => {
  if (route.name === 'chat') return '对话寻源'
  if (route.name === 'procure') return '寻源工作流'
  if (route.name === 'history') return '历史记录'
  if (route.name === 'supplier-dashboard') return '供应商工作台'
  if (route.name === 'supplier-products') return '产品管理'
  if (route.name === 'supplier-leads') return '线索管理'
  if (route.name === 'admin-audit') return '运营审核'
  if (route.name === 'company-assistant') return '企业 AI 助手'
  if (route.name === 'company-chat') return '企业问答'
  if (route.name === 'admin-knowledge') return '知识库管理'
  return '产品功能'
})

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
          <span class="brand__sub">智配采购工作台</span>
        </span>
      </RouterLink>
    </div>

    <nav class="sidebar__nav" aria-label="主导航">
      <RouterLink to="/chat" class="nav__link">
        <span class="nav__icon">💬</span>
        <span>对话寻源</span>
      </RouterLink>
      <RouterLink to="/company-chat" class="nav__link">
        <span class="nav__icon">🏢</span>
        <span>企业问答</span>
      </RouterLink>
      <RouterLink to="/company-assistant" class="nav__link">
        <span class="nav__icon">🤖</span>
        <span>企业 AI 助手</span>
      </RouterLink>
      <RouterLink to="/app" class="nav__link">
        <span class="nav__icon">⌘</span>
        <span>工作流寻源</span>
      </RouterLink>
      <RouterLink to="/history" class="nav__link">
        <span class="nav__icon">◷</span>
        <span>历史记录</span>
      </RouterLink>
      <RouterLink to="/" class="nav__link nav__link--landing">
        <span class="nav__icon">↗</span>
        <span>产品介绍页</span>
      </RouterLink>
    </nav>

    <div class="sidebar__section">
      <p class="sidebar__label">供应商端</p>
      <RouterLink to="/supplier" class="nav__link">
        <span class="nav__icon">📊</span>
        <span>供应商工作台</span>
      </RouterLink>
      <RouterLink to="/supplier/products" class="nav__link">
        <span class="nav__icon">📦</span>
        <span>产品管理</span>
      </RouterLink>
      <RouterLink to="/supplier/leads" class="nav__link">
        <span class="nav__icon">📋</span>
        <span>线索管理</span>
      </RouterLink>
    </div>

    <div class="sidebar__section">
      <p class="sidebar__label">运营</p>
      <RouterLink to="/admin/audit" class="nav__link">
        <span class="nav__icon">✓</span>
        <span>审核管理</span>
      </RouterLink>
      <RouterLink to="/admin/knowledge" class="nav__link">
        <span class="nav__icon">📚</span>
        <span>知识库管理</span>
      </RouterLink>
    </div>

    <div class="sidebar__notice">
      <b>事实边界</b>
      <p>供应商结果仅表示能力匹配，不代表实时库存、报价或交期承诺。</p>
    </div>
  </aside>

  <header class="topbar">
    <div class="topbar__left">
      <span class="topbar__crumb">MatchForge</span>
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
  background: rgba(10, 11, 15, 0.92);
  border-right: 1px solid var(--border-default);
  backdrop-filter: blur(18px);
}
.sidebar__brand {
  padding: var(--space-1) var(--space-1) var(--space-4);
}
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
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.28), transparent 42%),
    var(--gradient-accent);
  box-shadow: 0 0 28px rgba(99, 102, 241, 0.24);
}
.brand__name {
  display: block;
  font-weight: 700;
  font-size: var(--font-size-md);
  line-height: 1.1;
}
.brand__sub {
  display: block;
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0 var(--space-5);
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
.nav__link:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}
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
}
.sidebar__section {
  padding-top: var(--space-2);
}
.sidebar__label {
  margin-bottom: var(--space-2);
  padding: 0 10px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.scope-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.scope-list span {
  padding: 7px 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  border-radius: var(--radius-md);
}
.sidebar__notice {
  margin-top: auto;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.01));
}
.sidebar__notice b {
  display: block;
  margin-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.sidebar__notice p {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.6;
}

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
  background: rgba(10, 11, 15, 0.76);
  border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(18px);
}
.topbar__left,
.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.topbar__crumb,
.topbar__slash {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
.topbar__title {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
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
    height: 48px;
    padding: 0 var(--space-3);
    flex-direction: row;
    align-items: center;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
  }
  .sidebar__brand {
    padding: 0;
  }
  .brand__sub,
  .sidebar__section,
  .sidebar__notice {
    display: none;
  }
  .sidebar__nav {
    flex-direction: row;
    padding: 0;
    margin-left: var(--space-4);
    border-top: none;
  }
  .topbar {
    top: 48px;
    left: 0;
    height: 56px;
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
